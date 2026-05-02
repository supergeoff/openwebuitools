"""
title: Honcho Memory Filter
author: Assistant
author_url: https://github.com/open-webui
git_url: https://github.com/open-webui/open-webui
description: >
  Proactive conversational memory filter using Honcho (honcho.dev).
  Automatically injects stored user context into the system prompt (inlet)
  and persists every conversation turn to Honcho (outlet) for long-term
  memory and retrieval across sessions.
  Multi-user: each user configures their own API key, workspace, and display name.
  Requires: honcho-ai
requirements: honcho-ai
version: 2.0.0
license: MIT
"""

import hashlib
import logging
import os
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(_handler)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
_CLIENT_CACHE: Dict[tuple, Any] = {}

# Thread-safe set of message IDs already persisted to Honcho.
# Format: "{workspace_id}:{session_id}:{message_idx}" — we use a simple
# counter-based key because OpenWebUI does not expose per-message UUIDs
# inside the filter body.
_SAVED_TURNS: Set[str] = set()
_SAVED_LOCK = threading.Lock()

# Cache context results to avoid repeated API calls within a short window.
_CONTEXT_CACHE: Dict[str, tuple] = {}  # key -> (timestamp, context_text)
_CONTEXT_CACHE_TTL = 30  # seconds

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sanitize_id(raw_id: str) -> str:
    """Sanitize an identifier so it is safe for Honcho."""
    return "".join(c for c in raw_id if c.isalnum() or c in "-_.@").strip()


def _build_session_id(chat_id: str, workspace_id: str) -> str:
    """Build a deterministic, unique session id from OpenWebUI metadata."""
    return f"owui-{workspace_id}-{chat_id}"


def _get_honcho_client(
    api_key: str,
    workspace_id: str,
    base_url: Optional[str] = None,
    cache_user_id: str = "",
):
    """Return a cached Honcho client or create a new one.

    The ``cache_user_id`` is derived from the OpenWebUI user identity so
    that different end-users (who may have different personal API keys)
    never share a client instance.
    """
    from honcho import Honcho

    cache_key = (api_key, workspace_id, base_url, cache_user_id)
    if cache_key not in _CLIENT_CACHE:
        kwargs: Dict[str, Any] = {"api_key": api_key, "workspace_id": workspace_id}
        if base_url:
            kwargs["base_url"] = base_url
        # get_or_create semantics: instantiating Honcho with a workspace_id
        # that does not exist yet will create it automatically in current SDKs.
        _CLIENT_CACHE[cache_key] = Honcho(**kwargs)
        logger.info(
            "Filter created new Honcho client for workspace=%s user=%s",
            workspace_id,
            cache_user_id,
        )
    return _CLIENT_CACHE[cache_key]


def _turn_key(workspace_id: str, session_id: str, turn_index: int) -> str:
    """Return a unique key for a conversation turn."""
    return f"{workspace_id}:{session_id}:{turn_index}"


def _get_context_cache(key: str) -> Optional[str]:
    """Return cached context if still fresh."""
    entry = _CONTEXT_CACHE.get(key)
    if entry is None:
        return None
    ts, text = entry
    if time.time() - ts > _CONTEXT_CACHE_TTL:
        del _CONTEXT_CACHE[key]
        return None
    return text


def _set_context_cache(key: str, text: str) -> None:
    """Store context in the short-lived cache."""
    _CONTEXT_CACHE[key] = (time.time(), text)


# ---------------------------------------------------------------------------
# Filter class
# ---------------------------------------------------------------------------


class Filter:
    """
    OpenWebUI Filter that transparently integrates Honcho memory.

    **Inlet** (before the LLM call):
      1. Identifies the user + session.
      2. Fetches the user's Honcho context (peer card + recent memories).
      3. Injects a compact memory preamble into the system prompt.

    **Outlet** (after the LLM response):
      1. Saves the latest user message + assistant reply into Honcho.
      2. This feeds Honcho's background reasoning engine so future
         sessions can retrieve insights about the user.
    """

    # ------------------------------------------------------------------
    # Valves — admin configuration
    # ------------------------------------------------------------------
    class Valves(BaseModel):
        base_url: str = Field(
            default="",
            description="Custom Honcho API base URL (e.g. http://localhost:8000). Optional.",
        )
        assistant_peer_id: str = Field(
            default="openwebui-assistant",
            description="Peer ID used for the AI assistant inside Honcho.",
        )
        enable_context_injection: bool = Field(
            default=True,
            description="If True, inject stored memory into the system prompt.",
        )
        enable_auto_save: bool = Field(
            default=True,
            description="If True, automatically persist conversation turns to Honcho.",
        )
        context_tokens: int = Field(
            default=4_000,
            description="Token budget for the context injected into the prompt.",
        )
        injection_prefix: str = Field(
            default="[Honcho Memory]",
            description="Header prefix shown in the injected system prompt.",
        )

    # ------------------------------------------------------------------
    # UserValves — personal credentials & identity (per-user)
    # ------------------------------------------------------------------
    class UserValves(BaseModel):
        api_key: str = Field(
            default="",
            description="Your personal Honcho API key. Get it at app.honcho.dev.",
        )
        workspace_id: str = Field(
            default="openwebui",
            description="Honcho workspace ID. Created automatically if it doesn't exist.",
        )
        username: str = Field(
            default="",
            description="Your display name in Honcho memory (used as peer ID). If empty, falls back to your OpenWebUI user name or ID.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_credentials(
        self, user_valves: Optional[Any] = None
    ) -> tuple:
        """Resolve (api_key, workspace_id, base_url) with fallbacks.

        Priority:
          api_key   -> user_valves.api_key -> self.user_valves.api_key
                       -> HONCHO_API_KEY env var
          workspace -> user_valves.workspace_id -> self.user_valves.workspace_id
                       -> "openwebui"
          base_url  -> self.valves.base_url -> HONCHO_BASE_URL env var -> None
        """
        api_key = (
            (getattr(user_valves, "api_key", "") if user_valves else "")
            or self.user_valves.api_key
            or os.environ.get("HONCHO_API_KEY", "")
        )
        workspace_id = (
            (getattr(user_valves, "workspace_id", "") if user_valves else "")
            or self.user_valves.workspace_id
            or "openwebui"
        )
        base_url = (
            self.valves.base_url
            or os.environ.get("HONCHO_BASE_URL", "")
        ) or None
        return api_key, workspace_id, base_url

    def _resolve_user_peer_id(
        self,
        user_valves: Optional[Any] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        """Derive the Honcho peer_id for the human user.

        Priority:
          user_valves.username -> self.user_valves.username
          -> __user__["name"] -> __user__["id"] -> "anonymous"
        """
        if user_valves and getattr(user_valves, "username", ""):
            return _sanitize_id(user_valves.username)
        if self.user_valves.username:
            return _sanitize_id(self.user_valves.username)
        if __user__:
            if __user__.get("name"):
                return _sanitize_id(__user__["name"])
            if __user__.get("id"):
                return _sanitize_id(str(__user__["id"]))
        return "anonymous"

    def _get_cache_user_id(
        self,
        api_key: str,
        workspace_id: str,
        openwebui_user_id: str,
    ) -> str:
        """Build a short, privacy-safe cache identifier."""
        return hashlib.sha256(
            f"{api_key}:{workspace_id}:{openwebui_user_id}".encode()
        ).hexdigest()[:16]

    def _get_client(
        self, user_valves: Optional[dict] = None, user_id: str = ""
    ):
        api_key, workspace_id, base_url = self._resolve_credentials(user_valves)
        cache_user_id = self._get_cache_user_id(api_key, workspace_id, user_id)
        return _get_honcho_client(api_key, workspace_id, base_url, cache_user_id)

    def _ensure_session(
        self,
        user_id: str,
        chat_id: str,
        user_valves: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ):
        """Get-or-create peers and session, add peers if needed."""
        api_key, workspace_id, base_url = self._resolve_credentials(user_valves)
        cache_user_id = self._get_cache_user_id(api_key, workspace_id, user_id)
        client = _get_honcho_client(api_key, workspace_id, base_url, cache_user_id)

        safe_user = self._resolve_user_peer_id(user_valves, __user__)
        assistant_id = self.valves.assistant_peer_id
        session_id = _build_session_id(chat_id, workspace_id)

        user_peer = client.peer(safe_user)
        assistant_peer = client.peer(assistant_id)
        session = client.session(session_id)

        # Try to add peers — this is idempotent on the server side,
        # but we wrap it in a broad try/except so a network hiccup
        # does not break the conversation.
        try:
            session.add_peers([user_peer, assistant_peer])
        except Exception as exc:
            logger.debug("add_peers call failed (may already exist): %s", exc)

        return user_peer, assistant_peer, session

    def _fetch_memory_context(
        self,
        user_peer,
        assistant_peer,
        session,
    ) -> str:
        """Build a compact memory string to inject into the system prompt."""
        try:
            # Try the context endpoint first (most comprehensive)
            ctx = session.context(
                summary=True,
                tokens=self.valves.context_tokens,
                peer_target=user_peer.id,
                peer_perspective=assistant_peer.id,
            )
        except Exception as exc:
            logger.warning("session.context() failed, falling back to peer card: %s", exc)
            ctx = None

        parts = []

        # Peer card (stable facts)
        try:
            card = user_peer.get_card()
            if card:
                if isinstance(card, list):
                    parts.append("User Profile:")
                    for fact in card:
                        parts.append(f"  - {fact}")
                else:
                    parts.append(f"User Profile: {card}")
        except Exception as exc:
            logger.debug("Could not retrieve peer card: %s", exc)

        # Session context additions
        if ctx:
            # Summary
            try:
                if hasattr(ctx, "summary") and ctx.summary:
                    summary_content = getattr(ctx.summary, "content", str(ctx.summary))
                    if summary_content:
                        parts.append(f"Session Summary: {summary_content}")
            except Exception:
                pass

            # Representation
            try:
                if hasattr(ctx, "peer_representation") and ctx.peer_representation:
                    parts.append(f"User Insights: {ctx.peer_representation}")
            except Exception:
                pass

            # Recent messages (last few only)
            try:
                if hasattr(ctx, "messages") and ctx.messages:
                    recent = ctx.messages[-5:]
                    if recent:
                        parts.append("Recent exchanges:")
                        for msg in recent:
                            peer = getattr(msg, "peer_id", "?")
                            content = getattr(msg, "content", str(msg))
                            # Truncate very long messages
                            if len(content) > 200:
                                content = content[:200] + "..."
                            parts.append(f'  {peer}: "{content}"')
            except Exception:
                pass

        if not parts:
            return ""

        prefix = self.valves.injection_prefix
        return f"\n\n{prefix}\n" + "\n".join(parts) + f"\n{prefix}\n"

    # ==================================================================
    # INLET — called before the LLM
    # ==================================================================

    async def inlet(
        self,
        body: dict,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> dict:
        """
        Intercept the request before it reaches the LLM.

        If *enable_context_injection* is True, fetch the user's Honcho
        memory and prepend it to the system prompt so the model is
        aware of past conversations and user preferences.
        """
        if not self.valves.enable_context_injection:
            return body

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
            chat_id = (
                __metadata__.get("chat_id", "default") if __metadata__ else "default"
            )
            _, workspace_id, _ = self._resolve_credentials(user_valves)

            # Short-lived cache key
            cache_key = f"ctx:{workspace_id}:{chat_id}:{user_id}"
            cached = _get_context_cache(cache_key)
            if cached is not None:
                memory_text = cached
            else:
                user_peer, assistant_peer, session = self._ensure_session(
                    user_id, chat_id, user_valves=user_valves, __user__=__user__
                )
                memory_text = self._fetch_memory_context(
                    user_peer, assistant_peer, session
                )
                _set_context_cache(cache_key, memory_text)

            if not memory_text:
                return body

            # Inject into the system prompt
            messages: List[dict] = list(body.get("messages", []))
            if messages and messages[0].get("role") == "system":
                original = messages[0].get("content", "")
                if memory_text.strip() not in original:
                    messages[0]["content"] = original + "\n" + memory_text
            else:
                messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant.\n{memory_text}",
                    },
                )

            body["messages"] = messages
            logger.debug("Injected Honcho memory context (%d chars)", len(memory_text))

        except Exception as exc:
            # NEVER crash the conversation because of a memory backend hiccup
            logger.error("Honcho inlet error: %s", exc, exc_info=True)

        return body

    # ==================================================================
    # OUTLET — called after the LLM responds
    # ==================================================================

    async def outlet(
        self,
        body: dict,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> dict:
        """
        Intercept the response after the LLM has replied.

        If *enable_auto_save* is True, persist the latest user message
        and the assistant's reply to Honcho so they can be used for
        future context retrieval and background reasoning.
        """
        if not self.valves.enable_auto_save:
            return body

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
            chat_id = (
                __metadata__.get("chat_id", "default") if __metadata__ else "default"
            )
            _, workspace_id, _ = self._resolve_credentials(user_valves)

            user_peer, assistant_peer, session = self._ensure_session(
                user_id, chat_id, user_valves=user_valves, __user__=__user__
            )

            messages: List[dict] = list(body.get("messages", []))
            if len(messages) < 2:
                return body

            # Find the last user message and the last assistant message
            last_user_msg = None
            last_assistant_msg = None
            for msg in reversed(messages):
                role = msg.get("role", "")
                if role == "user" and last_user_msg is None:
                    last_user_msg = msg.get("content", "")
                elif role == "assistant" and last_assistant_msg is None:
                    last_assistant_msg = msg.get("content", "")
                if last_user_msg is not None and last_assistant_msg is not None:
                    break

            if not last_user_msg:
                return body

            # Build a turn key for deduplication — based on content hash
            content_hash = hashlib.sha256(
                f"{last_user_msg}:{last_assistant_msg or ''}".encode()
            ).hexdigest()[:16]
            turn_key = _turn_key(workspace_id, session.id, 0) + ":" + content_hash

            with _SAVED_LOCK:
                if turn_key in _SAVED_TURNS:
                    logger.debug("Turn already saved, skipping duplicate")
                    return body
                _SAVED_TURNS.add(turn_key)

            # Persist to Honcho
            honcho_messages = [user_peer.message(last_user_msg)]
            if last_assistant_msg:
                honcho_messages.append(assistant_peer.message(last_assistant_msg))

            session.add_messages(honcho_messages)
            logger.debug(
                "Saved turn to Honcho: user=%d chars, assistant=%d chars",
                len(last_user_msg),
                len(last_assistant_msg or ""),
            )

        except Exception as exc:
            logger.error("Honcho outlet error: %s", exc, exc_info=True)

        return body