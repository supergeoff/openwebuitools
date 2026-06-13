"""
title: system
author: geoff
requirements: langfuse
description: >
  Single source of truth for the system prompt across ALL models.
  The prompt itself lives in Langfuse (project "owui", text prompt "global",
  label "production"). This filter fetches it (cached) and injects it as the
  system message on every request.
  It can also fetch Hindsight memory and inject it with bankid set to the
  OpenWebUI user name so each user gets a separate memory bank.
  If Langfuse or Hindsight is unreachable, the chat request still proceeds.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

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
        hindsight_enabled: bool = Field(
            default=True,
            description="Fetch and inject Hindsight memory for the current user.",
        )
        hindsight_host: str = Field(
            default="https://hindsight.supergeoff.top",
            description="Hindsight base URL.",
        )
        hindsight_path: str = Field(
            default="/recall",
            description="Hindsight endpoint path that accepts a JSON payload.",
        )
        hindsight_auth_header: str = Field(
            default="",
            description='Optional Authorization header value, e.g. "Bearer ..." or "Basic ...".',
            json_schema_extra={"input": {"type": "password"}},
        )
        hindsight_timeout_seconds: float = Field(
            default=10.0,
            description="Timeout for Hindsight memory fetches.",
        )
        hindsight_limit: int = Field(
            default=12,
            description="Maximum number of memory items requested from Hindsight.",
        )
        hindsight_injection_prefix: str = Field(
            default="[Hindsight Memory]",
            description="Header used for injected Hindsight memory.",
        )

    def __init__(self):
        self.valves = self.Valves()
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

    def _fetch_policy(self) -> str:
        """Fetch the prompt text from Langfuse (cached by the SDK). Fail open."""
        client = self._get_client()
        if client is None:
            return FALLBACK_POLICY
        try:
            prompt = client.get_prompt(
                self.valves.prompt_name,
                label=self.valves.prompt_label,
                cache_ttl_seconds=self.valves.cache_ttl_seconds,
            )
            # Text prompt: compile() with no variables returns the raw string.
            text = prompt.compile()
            return text if isinstance(text, str) and text.strip() else FALLBACK_POLICY
        except Exception as exc:
            log.warning("Langfuse get_prompt failed (%s), using fallback.", exc)
            return FALLBACK_POLICY

    def _resolve_bankid(self, __user__: Optional[dict]) -> str:
        """Use the OpenWebUI user name as Hindsight bankid, with stable fallbacks."""
        if not __user__:
            return "anonymous"
        for key in ("name", "email", "id"):
            value = __user__.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return "anonymous"

    def _last_user_message(self, body: dict) -> str:
        for message in reversed(body.get("messages", [])):
            if message.get("role") == "user":
                content = message.get("content", "")
                if isinstance(content, str):
                    return content
                try:
                    return json.dumps(content, ensure_ascii=False)
                except TypeError:
                    return str(content)
        return ""

    def _hindsight_url(self) -> str:
        host = self.valves.hindsight_host.rstrip("/")
        path = self.valves.hindsight_path or ""
        if path and not path.startswith("/"):
            path = f"/{path}"
        return f"{host}{path}"

    def _coerce_hindsight_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts = [self._coerce_hindsight_text(item) for item in value]
            return "\n".join(part for part in parts if part)
        if isinstance(value, dict):
            for key in (
                "context",
                "memory",
                "memories",
                "result",
                "results",
                "answer",
                "content",
                "text",
            ):
                if key in value:
                    text = self._coerce_hindsight_text(value[key])
                    if text:
                        return text
            if {"role", "content"} <= value.keys():
                return self._coerce_hindsight_text(value["content"])
            return ""
        return str(value).strip()

    def _fetch_hindsight_memory(
        self,
        bankid: str,
        body: dict,
        __user__: Optional[dict],
    ) -> str:
        """Fetch memory from Hindsight. It must receive bankid per OpenWebUI user."""
        if not self.valves.hindsight_enabled:
            return ""
        if not self.valves.hindsight_host:
            return ""

        try:
            payload = {
                "bankid": bankid,
                "query": self._last_user_message(body),
                "messages": body.get("messages", []),
                "limit": self.valves.hindsight_limit,
                "user": {
                    "id": (__user__ or {}).get("id"),
                    "email": (__user__ or {}).get("email"),
                    "name": (__user__ or {}).get("name"),
                },
            }
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
            if self.valves.hindsight_auth_header:
                headers["Authorization"] = self.valves.hindsight_auth_header

            request = urllib.request.Request(
                self._hindsight_url(),
                data=data,
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(
                request, timeout=self.valves.hindsight_timeout_seconds
            ) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            log.warning("Hindsight request failed with HTTP %s.", exc.code)
            return ""
        except Exception as exc:
            log.warning("Hindsight request failed: %s", exc)
            return ""

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw

        return self._coerce_hindsight_text(parsed)

    def _build_injected_prompt(
        self,
        policy: str,
        body: dict,
        __user__: Optional[dict],
    ) -> str:
        sections = [policy.strip()]
        bankid = self._resolve_bankid(__user__)
        memory = self._fetch_hindsight_memory(bankid, body, __user__)
        if memory:
            prefix = self.valves.hindsight_injection_prefix.strip()
            sections.append(f"{prefix}\n{memory.strip()}" if prefix else memory.strip())
        return "\n\n".join(section for section in sections if section)

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.enabled:
            return body

        policy = self._fetch_policy()
        if not policy:
            return body

        injected_prompt = self._build_injected_prompt(policy, body, __user__)
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
