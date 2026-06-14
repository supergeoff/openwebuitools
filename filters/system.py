"""
title: system
author: geoff
requirements: langfuse
description: >
  Single source of truth for the system prompt across ALL models.
  The prompt itself lives in Langfuse (project "owui", text prompt "global",
  label "production"). This filter fetches it (cached) and injects it as the
  system message on every request.
  The only per-user runtime value managed here is hindsight_bankid, exposed to
  the Langfuse prompt as {{hindsight_bankid}}.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger("global_policy_filter")

# Used only if Langfuse cannot be reached. Keep it roughly in sync with the
# Langfuse "production" version so a fetch failure degrades gracefully.
FALLBACK_POLICY = (
    """You are an autonomous operator for the user. Act, do not propose."""
)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Filter execution priority (lower runs first)."
        )
        enabled: bool = Field(
            default=True, description="Inject the prompt on every request."
        )
        langfuse_host: str = Field(
            default="https://langfuse.supergeoff.top",
            description="Langfuse base URL.",
        )
        langfuse_public_key: str = Field(
            default="",
            description="Langfuse public key (pk-lf-...).",
            json_schema_extra={"input": {"type": "password"}},
        )
        langfuse_secret_key: str = Field(
            default="",
            description="Langfuse secret key (sk-lf-...).",
            json_schema_extra={"input": {"type": "password"}},
        )
        prompt_name: str = Field(
            default="global",
            description="Name of the TEXT prompt in Langfuse (project owui).",
        )
        prompt_label: str = Field(
            default="production",
            description="Langfuse label to fetch (e.g. production, latest).",
        )
        cache_ttl_seconds: int = Field(
            default=300,
            description="Langfuse SDK cache TTL. Edits propagate after this delay.",
        )
        forced_tool_ids: str = Field(
            default="",
            description=(
                "Comma-separated workspace tool IDs to force-enable on every request."
            ),
        )

    class UserValves(BaseModel):
        hindsight_bankid: str = Field(
            default="",
            description="Per-user Hindsight bankid passed to the Langfuse prompt.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()
        self._client = None
        self._warned_unresolved_tool_ids = set()

    def _get_client(self):
        """Lazily build a Langfuse client. Returns None if keys are missing."""
        if self._client is not None:
            return self._client
        if not (self.valves.langfuse_public_key and self.valves.langfuse_secret_key):
            return None
        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=self.valves.langfuse_public_key,
                secret_key=self.valves.langfuse_secret_key,
                host=self.valves.langfuse_host,
            )
            return self._client
        except Exception as exc:
            log.warning("Langfuse client init failed: %s", exc)
            return None

    def _compile_fallback(self, variables: dict) -> str:
        bankid = variables.get("hindsight_bankid", "")
        if not bankid:
            return FALLBACK_POLICY
        return f"{FALLBACK_POLICY}\n\nhindsight_bankid: {bankid}"

    def _fetch_policy(self, variables: dict) -> str:
        """Fetch the prompt text from Langfuse (cached by the SDK). Fail open."""
        client = self._get_client()
        if client is None:
            return self._compile_fallback(variables)
        try:
            prompt = client.get_prompt(
                self.valves.prompt_name,
                label=self.valves.prompt_label,
                cache_ttl_seconds=self.valves.cache_ttl_seconds,
            )
            text = prompt.compile(**variables)
            return (
                text
                if isinstance(text, str) and text.strip()
                else self._compile_fallback(variables)
            )
        except Exception as exc:
            log.warning("Langfuse get_prompt failed (%s), using fallback.", exc)
            return self._compile_fallback(variables)

    def _get_user_valve(self, __user__: Optional[dict], key: str) -> Optional[str]:
        """Read OpenWebUI UserValves from dict or Pydantic-style objects."""
        if not __user__:
            return ""
        user_valves = (__user__.get("valves", {}) if __user__ else {}) or {}
        if isinstance(user_valves, dict):
            return user_valves.get(key, "")
        if hasattr(user_valves, "model_dump"):
            return user_valves.model_dump().get(key, "")
        if hasattr(user_valves, "dict"):
            return user_valves.dict().get(key, "")
        return getattr(user_valves, key, "")

    def _resolve_bankid(self, __user__: Optional[dict]) -> str:
        """Use only the explicit per-user Hindsight bankid valve."""
        value = self._get_user_valve(__user__, "hindsight_bankid")
        if not value:
            value = self.user_valves.hindsight_bankid
        return str(value).strip() if value else ""

    def _prompt_variables(self, __user__: Optional[dict]) -> dict:
        return {"hindsight_bankid": self._resolve_bankid(__user__)}

    def _build_injected_prompt(
        self,
        __user__: Optional[dict],
    ) -> str:
        variables = self._prompt_variables(__user__)
        return self._fetch_policy(variables).strip()

    def _dedupe_tool_ids(self, tool_ids) -> list[str]:
        result = []
        seen = set()
        for tool_id in tool_ids:
            value = str(tool_id).strip() if tool_id is not None else ""
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _parse_forced_tool_ids(self) -> list[str]:
        raw = str(self.valves.forced_tool_ids or "")
        return self._dedupe_tool_ids(raw.replace("\n", ",").split(","))

    def _coerce_tool_ids(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return self._dedupe_tool_ids([value])
        if isinstance(value, (list, tuple, set)):
            return self._dedupe_tool_ids(value)
        return []

    def _get_unresolved_mcp_tool_ids(
        self, forced_tool_ids: list[str], __request__=None
    ) -> list[str]:
        mcp_tool_ids = [
            tool_id
            for tool_id in forced_tool_ids
            if tool_id.startswith("server:mcp:")
        ]
        if not mcp_tool_ids or __request__ is None:
            return []

        try:
            connections = __request__.app.state.config.TOOL_SERVER_CONNECTIONS
        except AttributeError:
            return []

        configured_server_ids = {
            str(connection.get("info", {}).get("id", "")).strip()
            for connection in connections or []
            if connection.get("type") == "mcp"
        }

        return [
            tool_id
            for tool_id in mcp_tool_ids
            if tool_id[len("server:mcp:") :] not in configured_server_ids
        ]

    async def _get_unresolved_forced_tool_ids(
        self, forced_tool_ids: list[str], __request__=None
    ) -> list[str]:
        local_tool_ids = [
            tool_id
            for tool_id in forced_tool_ids
            if not tool_id.startswith("server:mcp:")
        ]
        unresolved_tool_ids = self._get_unresolved_mcp_tool_ids(
            forced_tool_ids, __request__
        )

        if local_tool_ids:
            try:
                from open_webui.models.tools import Tools

                tool_models = await Tools.get_tools_by_ids(local_tool_ids)
            except ImportError:
                tool_models = {}
            except Exception as exc:
                log.warning("Could not validate forced tool_ids: %s", exc)
                tool_models = {}

            resolved_tool_ids = (
                set(tool_models.keys()) if isinstance(tool_models, dict) else set()
            )
            unresolved_tool_ids.extend(
                [
                    tool_id
                    for tool_id in local_tool_ids
                    if tool_id not in resolved_tool_ids
                ]
            )

        return unresolved_tool_ids

    def _log_unresolved_forced_tool_ids(self, unresolved_tool_ids: list[str]) -> None:
        new_unresolved = [
            tool_id
            for tool_id in unresolved_tool_ids
            if tool_id not in self._warned_unresolved_tool_ids
        ]
        if not new_unresolved:
            return

        self._warned_unresolved_tool_ids.update(new_unresolved)
        log.warning(
            "Forced tool_ids could not be resolved and may be ignored: %s",
            ", ".join(new_unresolved),
        )

    async def _force_tool_ids(self, body: dict, __request__=None) -> None:
        forced_tool_ids = self._parse_forced_tool_ids()
        if not forced_tool_ids:
            return

        body["tool_ids"] = self._dedupe_tool_ids(
            [*self._coerce_tool_ids(body.get("tool_ids")), *forced_tool_ids]
        )

        unresolved_tool_ids = await self._get_unresolved_forced_tool_ids(
            forced_tool_ids, __request__
        )
        self._log_unresolved_forced_tool_ids(unresolved_tool_ids)

    async def inlet(
        self, body: dict, __request__=None, __user__: Optional[dict] = None
    ) -> dict:
        await self._force_tool_ids(body, __request__)

        if not self.valves.enabled:
            return body

        injected_prompt = self._build_injected_prompt(__user__)
        if not injected_prompt:
            return body

        messages = list(body.get("messages", []))
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content", "")
            messages[0]["content"] = (
                f"{injected_prompt}\n\n{existing}" if existing else injected_prompt
            )
        else:
            messages.insert(0, {"role": "system", "content": injected_prompt})
        body["messages"] = messages
        return body
