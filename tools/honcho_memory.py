"""
title: Honcho Memory Tool
author: Assistant
author_url: https://github.com/open-webui
git_url: https://github.com/open-webui/open-webui
description: >
  Integration with Honcho (honcho.dev) conversational memory platform.
  Provides explicit tools for the LLM to save memories, search past memories,
  retrieve user context, ask questions about the user, and get their profile.
  Multi-user: each user configures their own API key, workspace, and display name.
  Requires: honcho-ai
requirements: honcho-ai
version: 2.0.0
license: MIT
"""

import hashlib
import logging
import os
from typing import Any, Callable, Dict, List, Optional

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
# Global client cache — avoids re-creating the Honcho client on every call.
# Keys are tuples (api_key, workspace_id, base_url, cache_user_id) so multiple
# configs and multiple OpenWebUI users can coexist safely.
# ---------------------------------------------------------------------------
_CLIENT_CACHE: Dict[tuple, Any] = {}


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
            "Tool created new Honcho client for workspace=%s user=%s",
            workspace_id,
            cache_user_id,
        )
    return _CLIENT_CACHE[cache_key]


def _clear_client_cache() -> None:
    """Clear the client cache — useful when credentials change."""
    global _CLIENT_CACHE
    _CLIENT_CACHE = {}
    logger.info("Honcho client cache cleared")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize_id(raw_id: str) -> str:
    """Sanitize an identifier so it is safe for Honcho (alnum, dash, underscore)."""
    return "".join(c for c in raw_id if c.isalnum() or c in "-_.@").strip()


def _build_session_id(chat_id: str, workspace_id: str) -> str:
    """Build a deterministic, unique session id from OpenWebUI metadata."""
    return f"owui-{workspace_id}-{chat_id}"


async def _emit(
    emitter: Optional[Callable[[dict], Any]],
    message: str,
    done: bool = False,
) -> None:
    """Send a status event back to the OpenWebUI front-end."""
    if emitter is None:
        return
    try:
        await emitter(
            {
                "type": "status" if not done else "status",
                "data": {"description": message, "done": done},
            }
        )
    except Exception as exc:
        logger.debug("Failed to emit status: %s", exc)


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------


class Tools:
    """
    OpenWebUI Tool exposing Honcho conversational memory capabilities.

    Available functions
    -------------------
    - **save_memory**     : Persist an important fact / observation to Honcho.
    - **search_memories** : Search previously stored memories (hybrid search).
    - **get_user_context**: Retrieve full conversation context + representations.
    - **ask_about_user**  : Ask Honcho a natural-language question about the user.
    - **get_user_profile**: Get the peer card (synthetic user profile).
    """

    # ------------------------------------------------------------------
    # Valves — admin-configurable settings
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
        context_tokens: int = Field(
            default=8_000,
            description="Default token budget for session.context() calls.",
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
        self, user_valves: Optional[dict] = None
    ) -> tuple:
        """Resolve (api_key, workspace_id, base_url) with fallbacks.

        Priority:
          api_key   -> user_valves["api_key"] -> self.user_valves.api_key
                       -> HONCHO_API_KEY env var
          workspace -> user_valves["workspace_id"] -> self.user_valves.workspace_id
                       -> "openwebui"
          base_url  -> self.valves.base_url -> HONCHO_BASE_URL env var -> None
        """
        uv = user_valves or {}
        api_key = (
            uv.get("api_key", "")
            or self.user_valves.api_key
            or os.environ.get("HONCHO_API_KEY", "")
        )
        workspace_id = (
            uv.get("workspace_id", "")
            or self.user_valves.workspace_id
            or "openwebui"
        )
        base_url = (
            self.valves.base_url
            or os.environ.get("HONCHO_BASE_URL", "")
        ) or None
        if not api_key:
            logger.warning(
                "No Honcho API key configured — using demo environment (limited)"
            )
        return api_key, workspace_id, base_url

    def _resolve_user_peer_id(
        self,
        user_valves: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ) -> str:
        """Derive the Honcho peer_id for the human user.

        Priority:
          user_valves["username"] -> self.user_valves.username
          -> __user__["name"] -> __user__["id"] -> "anonymous"
        """
        uv = user_valves or {}
        if uv.get("username"):
            return _sanitize_id(uv["username"])
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

    def _get_client(self, user_valves: Optional[dict] = None, user_id: str = ""):
        api_key, workspace_id, base_url = self._resolve_credentials(user_valves)
        cache_user_id = self._get_cache_user_id(api_key, workspace_id, user_id)
        return _get_honcho_client(api_key, workspace_id, base_url, cache_user_id)

    def _get_peers_and_session(
        self,
        user_id: str,
        chat_id: str,
        user_valves: Optional[dict] = None,
        __user__: Optional[dict] = None,
    ):
        """Get-or-create the user peer, assistant peer, and session."""
        api_key, workspace_id, base_url = self._resolve_credentials(user_valves)
        cache_user_id = self._get_cache_user_id(api_key, workspace_id, user_id)
        client = _get_honcho_client(api_key, workspace_id, base_url, cache_user_id)

        safe_user = self._resolve_user_peer_id(user_valves, __user__)
        assistant_id = self.valves.assistant_peer_id
        session_id = _build_session_id(chat_id, workspace_id)

        user_peer = client.peer(safe_user)
        assistant_peer = client.peer(assistant_id)
        session = client.session(session_id)
        return user_peer, assistant_peer, session

    # ==================================================================
    # PUBLIC TOOL METHODS — called by the LLM
    # ==================================================================

    async def save_memory(
        self,
        memory: str,
        category: str = "general",
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Save an important fact, observation, or memory to Honcho.

        Call this whenever you learn something important about the user
        (preferences, facts, events, opinions) that should persist across
        conversations.

        :param memory: The fact or observation to persist (free text).
        :param category: Optional category tag (e.g. 'preference', 'fact',
                         'event', 'opinion'). Defaults to 'general'.
        :return: Confirmation message.
        """
        await _emit(__event_emitter__, "Saving memory to Honcho...")

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            owui_user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
            chat_id = (
                __metadata__.get("chat_id", "default") if __metadata__ else "default"
            )

            user_peer, assistant_peer, session = self._get_peers_and_session(
                owui_user_id, chat_id, user_valves=user_valves, __user__=__user__
            )

            # Build a structured observation message
            formatted = f"[{category.upper()}] {memory}"

            # Persist as a message in the current session
            session.add_messages(
                [
                    user_peer.message(formatted),
                ]
            )

            await _emit(
                __event_emitter__, f"Memory saved ({category}): {memory[:80]}...", done=True
            )
            return f"Memory saved successfully in category '{category}': {memory}"

        except Exception as exc:
            logger.error("Failed to save memory: %s", exc, exc_info=True)
            await _emit(__event_emitter__, f"Error saving memory: {exc}", done=True)
            return f"Error saving memory: {exc}"

    async def search_memories(
        self,
        query: str,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Search the user's stored memories in Honcho.

        Use this to recall past facts, preferences, or events when the user
        refers to something from a previous conversation.

        :param query: Natural-language search query.
        :return: Formatted search results or a message if nothing is found.
        """
        await _emit(__event_emitter__, f"Searching memories for: {query}")

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            owui_user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"

            safe_user = self._resolve_user_peer_id(user_valves, __user__)
            client = self._get_client(user_valves, owui_user_id)
            user_peer = client.peer(safe_user)
            results = user_peer.search(query)

            if not results:
                await _emit(__event_emitter__, "No memories found.", done=True)
                return "No relevant memories found for this query."

            lines = [f"## Memory Search Results for: '{query}'\n"]
            for idx, item in enumerate(results[:10], 1):
                content = getattr(item, "content", str(item))
                lines.append(f"{idx}. {content}")

            result_text = "\n".join(lines)
            await _emit(
                __event_emitter__, f"Found {len(results)} memory(ies).", done=True
            )
            return result_text

        except Exception as exc:
            logger.error("Failed to search memories: %s", exc, exc_info=True)
            await _emit(__event_emitter__, f"Error searching memories: {exc}", done=True)
            return f"Error searching memories: {exc}"

    async def get_user_context(
        self,
        tokens: int = 0,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Retrieve the full conversation context for the current session.

        Returns messages, summaries, and peer representations formatted as
        a human-readable block. Use this when you need a comprehensive view
        of what has been discussed.

        :param tokens: Maximum token budget (0 = use default from Valves).
        :return: Formatted context string.
        """
        await _emit(__event_emitter__, "Retrieving user context from Honcho...")

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            owui_user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
            chat_id = (
                __metadata__.get("chat_id", "default") if __metadata__ else "default"
            )

            user_peer, assistant_peer, session = self._get_peers_and_session(
                owui_user_id, chat_id, user_valves=user_valves, __user__=__user__
            )

            token_budget = tokens or self.valves.context_tokens

            ctx = session.context(
                summary=True,
                tokens=token_budget,
                peer_target=user_peer.id,
                peer_perspective=assistant_peer.id,
            )

            parts = ["## Honcho Session Context\n"]

            # Summary
            if hasattr(ctx, "summary") and ctx.summary:
                summary_content = getattr(ctx.summary, "content", str(ctx.summary))
                parts.append(f"**Summary:** {summary_content}\n")

            # Messages
            if hasattr(ctx, "messages") and ctx.messages:
                parts.append("### Recent Messages\n")
                for msg in ctx.messages[-20:]:  # last 20 messages max
                    peer = getattr(msg, "peer_id", "?")
                    content = getattr(msg, "content", str(msg))
                    parts.append(f"- **{peer}**: {content}")
                parts.append("")

            # Peer representation
            if hasattr(ctx, "peer_representation") and ctx.peer_representation:
                parts.append(
                    f"### User Representation\n{ctx.peer_representation}\n"
                )

            # Peer card
            if hasattr(ctx, "peer_card") and ctx.peer_card:
                parts.append(f"### User Profile Card\n{ctx.peer_card}\n")

            result = "\n".join(parts)
            await _emit(__event_emitter__, "Context retrieved.", done=True)
            return result

        except Exception as exc:
            logger.error("Failed to get user context: %s", exc, exc_info=True)
            await _emit(__event_emitter__, f"Error retrieving context: {exc}", done=True)
            return f"Error retrieving context: {exc}"

    async def ask_about_user(
        self,
        question: str,
        reasoning_level: str = "medium",
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Ask Honcho a natural-language question about the user.

        This uses Honcho's reasoning engine to synthesize an answer from
        stored memories, representations, and conclusions.

        Example questions:
        - "What are this user's main interests?"
        - "What should I know before responding to this user?"
        - "Has this user mentioned any preferences about tone or style?"

        :param question: The question to ask about the user.
        :param reasoning_level: Reasoning effort — 'minimal', 'low', 'medium',
                               'high', or 'max'. Default is 'medium'.
        :return: Honcho's synthesized answer.
        """
        await _emit(__event_emitter__, f"Asking Honcho: {question[:60]}...")

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            owui_user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
            chat_id = (
                __metadata__.get("chat_id", "default") if __metadata__ else "default"
            )

            user_peer, assistant_peer, session = self._get_peers_and_session(
                owui_user_id, chat_id, user_valves=user_valves, __user__=__user__
            )

            response = user_peer.chat(
                question,
                target=assistant_peer.id,
                session=session.id,
                reasoning_level=reasoning_level,
            )

            answer = getattr(response, "content", str(response))
            await _emit(__event_emitter__, "Answer received from Honcho.", done=True)
            return f"**Honcho says:** {answer}"

        except Exception as exc:
            logger.error("Failed to ask about user: %s", exc, exc_info=True)
            await _emit(__event_emitter__, f"Error querying Honcho: {exc}", done=True)
            return f"Error querying Honcho: {exc}"

    async def get_user_profile(
        self,
        __user__: dict = None,
        __metadata__: dict = None,
        __event_emitter__: Callable[[dict], Any] = None,
    ) -> str:
        """
        Retrieve the synthetic profile (peer card) for the current user.

        The peer card contains stable biographical facts inferred by Honcho
        (name, preferences, background, interests, etc.).

        :return: Formatted peer card or a message if none exists yet.
        """
        await _emit(__event_emitter__, "Retrieving user profile...")

        try:
            user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
            owui_user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"

            safe_user = self._resolve_user_peer_id(user_valves, __user__)
            client = self._get_client(user_valves, owui_user_id)
            user_peer = client.peer(safe_user)

            card = user_peer.get_card()

            if not card:
                await _emit(
                    __event_emitter__, "No profile found yet.", done=True
                )
                return (
                    "No profile card exists for this user yet. "
                    "It will be generated automatically as conversations accumulate."
                )

            lines = ["## User Profile (Peer Card)\n"]
            if isinstance(card, list):
                for idx, fact in enumerate(card, 1):
                    lines.append(f"{idx}. {fact}")
            else:
                lines.append(str(card))

            result = "\n".join(lines)
            await _emit(__event_emitter__, "Profile retrieved.", done=True)
            return result

        except Exception as exc:
            logger.error("Failed to get user profile: %s", exc, exc_info=True)
            await _emit(__event_emitter__, f"Error retrieving profile: {exc}", done=True)
            return f"Error retrieving profile: {exc}"