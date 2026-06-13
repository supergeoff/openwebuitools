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

    class UserValves(BaseModel):
        hindsight_bankid: str = Field(
            default="",
            description="Per-user Hindsight bankid passed to the Langfuse prompt.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.user_valves = self.UserValves()
        self._client = None

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

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
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
