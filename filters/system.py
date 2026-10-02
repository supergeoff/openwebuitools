"""
title: system
author: geoff
requirements: langfuse
description: >
  Single source of truth for the system prompt across ALL models.
  The prompt itself lives in Langfuse as multiple text prompt modules, fetched
  concurrently (assembled in declaration order) and injected as the system
  message on every request. The only
  per-user runtime value managed here is hindsight_bankid, exposed to the
  memory prompt as {{hindsight_bankid}}.
  Also records one Langfuse trace per assistant message through the Langfuse v4
  OpenTelemetry endpoint (OTLP/HTTP JSON, x-langfuse-ingestion-version: 4).
  The trace id is derived from the seed "owui-{chat_id}-{message_id}" with the
  algorithm of Langfuse.create_trace_id(seed=...), so the langfuse_feedback
  action and any SDK user can compute it. Each span is exported once, complete:
  an "owui-chat-request" event at inlet time (failed requests still leave a
  trace with input, user and session), then the root "owui-chat" span at outlet
  time with the overall input and output.
  Agent gateway models (passthrough_model_prefixes, default "cptr/" for
  Open WebUI Computer) run their own agent loop and ignore Open WebUI tools,
  skills, terminals and system prompts: for them the filter keeps tracing but
  skips prompt injection and strips tool_ids, skill_ids and terminal_id, so
  Open WebUI no longer opens one MCP session per forced server on each message.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger("global_policy_filter")

TRACE_NAME = "owui-chat"
REQUEST_EVENT_NAME = "owui-chat-request"
INFLIGHT_LIMIT = 2048

PROMPT_MODULES = (
    "core",
    "task_management",
    "memory",
    "tools",
    "research",
    "coding",
    "output_style",
)
TRACE_TAGS = ("owui", "system")


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
        prompt_label: str = Field(
            default="production",
            description="Langfuse label to fetch (e.g. production, latest).",
        )
        cache_ttl_seconds: int = Field(
            default=900,
            description=(
                "Langfuse SDK prompt cache TTL. The SDK serves stale entries "
                "and refreshes in the background, so this only bounds how "
                "long prompt edits take to propagate."
            ),
        )
        enable_tracing: bool = Field(
            default=True,
            description=(
                "Record one Langfuse trace per assistant message "
                "(created at request time, completed at response time)."
            ),
        )
        forced_tool_ids: str = Field(
            default="",
            description=(
                "Comma-separated workspace tool IDs to force-enable on every request."
            ),
        )
        forced_skill_ids: str = Field(
            default="",
            description=(
                "Comma-separated workspace skill IDs to force-enable on every request."
            ),
        )
        passthrough_model_prefixes: str = Field(
            default="cptr/",
            description=(
                "Comma-separated model id prefixes of agent gateways (Open WebUI "
                "Computer: cptr/) that ignore Open WebUI tools and system prompts. "
                "For these models the filter only traces: no prompt injection, "
                "no forced tools or skills, and tool_ids, skill_ids and "
                "terminal_id are removed from the request."
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
        self._warned_unresolved_skill_ids = set()
        self._bg_tasks = set()
        self._clock_offset = None
        # Inlet time per trace seed, used as the root span start at outlet time.
        self._inflight_starts = OrderedDict()

    def _get_client(self):
        """Lazily build a Langfuse client. Raises clearly if unavailable."""
        if self._client is not None:
            return self._client
        if not (self.valves.langfuse_public_key and self.valves.langfuse_secret_key):
            raise RuntimeError(
                "Langfuse public and secret keys are required for system prompt injection."
            )
        try:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=self.valves.langfuse_public_key,
                secret_key=self.valves.langfuse_secret_key,
                host=self.valves.langfuse_host,
            )
            return self._client
        except Exception as exc:
            raise RuntimeError(f"Langfuse client init failed: {exc}") from exc

    def _prompt_module_names(self) -> list[str]:
        prompt_modules = self._dedupe_ids(PROMPT_MODULES)
        if not prompt_modules:
            raise RuntimeError(
                "At least one built-in Langfuse prompt module is required."
            )
        return prompt_modules

    def _fetch_prompt_module(self, prompt_name: str, variables: dict) -> str:
        """Fetch and compile one Langfuse prompt module. Fail closed."""
        client = self._get_client()
        try:
            prompt = client.get_prompt(
                prompt_name,
                label=self.valves.prompt_label,
                cache_ttl_seconds=self.valves.cache_ttl_seconds,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Langfuse prompt '{prompt_name}' label "
                f"'{self.valves.prompt_label}' fetch failed: {exc}"
            ) from exc

        try:
            text = prompt.compile(**variables)
        except Exception as exc:
            raise RuntimeError(
                f"Langfuse prompt '{prompt_name}' label "
                f"'{self.valves.prompt_label}' compile failed: {exc}"
            ) from exc

        if not isinstance(text, str) or not text.strip():
            raise RuntimeError(
                f"Langfuse prompt '{prompt_name}' compiled to empty text."
            )
        return text.strip()

    async def _fetch_policy(self, __user__: Optional[dict]) -> str:
        import asyncio

        # get_prompt is a blocking SDK call: run the fetches concurrently in
        # threads instead of serially on the event loop. gather preserves the
        # module declaration order, so the assembled prompt is unchanged.
        self._get_client()
        prompt_names = self._prompt_module_names()
        texts = await asyncio.gather(
            *(
                asyncio.to_thread(
                    self._fetch_prompt_module,
                    prompt_name,
                    self._prompt_variables(prompt_name, __user__),
                )
                for prompt_name in prompt_names
            )
        )
        return "\n\n".join(
            f"# Prompt Module: {prompt_name}\n\n{text}"
            for prompt_name, text in zip(prompt_names, texts)
        )

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

    def _prompt_variables(self, prompt_name: str, __user__: Optional[dict]) -> dict:
        if prompt_name != "memory":
            return {}
        return {"hindsight_bankid": self._resolve_bankid(__user__)}

    async def _build_injected_prompt(
        self,
        __user__: Optional[dict],
    ) -> str:
        return (await self._fetch_policy(__user__)).strip()

    def _trace_seed(self, chat_id: str, message_id: str) -> str:
        # Former plain trace id, kept as the seed of the OTEL ids and as the
        # owui_trace_key metadata so traces stay searchable by chat/message.
        return f"owui-{chat_id}-{message_id}"

    def _build_trace_id(self, chat_id: str, message_id: str) -> str:
        # Same algorithm as Langfuse.create_trace_id(seed=...) in the Python
        # SDK: 16 bytes of sha256(seed), hex. Shared with langfuse_feedback.
        seed = self._trace_seed(chat_id, message_id)
        return hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex()

    def _observation_id(self, chat_id: str, message_id: str, role: str) -> str:
        # Same algorithm as Langfuse.create_observation_id(seed=...): 8 bytes.
        seed = f"{self._trace_seed(chat_id, message_id)}:{role}"
        return hashlib.sha256(seed.encode("utf-8")).digest()[:8].hex()

    def _root_observation_id(self, chat_id: str, message_id: str) -> str:
        return self._observation_id(chat_id, message_id, "root")

    def _request_observation_id(self, chat_id: str, message_id: str) -> str:
        return self._observation_id(chat_id, message_id, "request")

    def _metadata_value(self, body: dict, __metadata__: Optional[dict], key: str):
        if __metadata__ and __metadata__.get(key) is not None:
            return __metadata__.get(key)
        metadata = body.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get(key) is not None:
            return metadata.get(key)
        return body.get(key)

    def _output_items_text(self, output) -> str:
        """Extract assistant text from OWUI's structured output items
        (type "message" -> content parts of type "output_text")."""
        if not isinstance(output, list):
            return ""
        texts = []
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            text = "".join(
                part.get("text", "")
                for part in item.get("content") or []
                if isinstance(part, dict) and part.get("type") == "output_text"
            )
            if text:
                texts.append(text)
        return "\n".join(texts)

    def _last_message_content(self, body: dict, role: str) -> str:
        for message in reversed(body.get("messages", []) or []):
            if message.get("role") == role:
                content = message.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                # Recent OpenWebUI stores assistant text in structured output
                # items and may leave "content" empty in the outlet body.
                if not content.strip() and role == "assistant":
                    content = self._output_items_text(message.get("output"))
                return content
        return ""

    def _model_id(self, body: dict, __model__=None) -> str:
        if body.get("model"):
            return str(body.get("model"))
        if isinstance(__model__, dict):
            return str(__model__.get("id", "") or "")
        return str(getattr(__model__, "id", "") or "") if __model__ else ""

    def _model_ids_for_matching(self, body: dict, __model__=None) -> list[str]:
        """Model id plus the base model id of a workspace model built on it."""
        ids = [self._model_id(body, __model__)]
        if isinstance(__model__, dict):
            ids.append(str(__model__.get("id", "") or ""))
            info = __model__.get("info") or {}
            if isinstance(info, dict):
                ids.append(str(info.get("base_model_id", "") or ""))
        return self._dedupe_ids(ids)

    def _parse_passthrough_prefixes(self) -> list[str]:
        raw = str(self.valves.passthrough_model_prefixes or "")
        return self._dedupe_ids(raw.replace("\n", ",").split(","))

    def _is_passthrough_model(self, body: dict, __model__=None) -> bool:
        prefixes = self._parse_passthrough_prefixes()
        if not prefixes:
            return False
        return any(
            model_id.startswith(prefix)
            for model_id in self._model_ids_for_matching(body, __model__)
            for prefix in prefixes
        )

    def _strip_owui_tooling(self, body: dict) -> None:
        """Agent gateways ignore OWUI tools: do not make OWUI resolve them."""
        for key in ("tool_ids", "skill_ids", "terminal_id"):
            body.pop(key, None)

    def _trace_metadata(
        self,
        body: dict,
        __metadata__: Optional[dict],
        __model__=None,
    ) -> dict:
        return {
            "chat_id": str(self._metadata_value(body, __metadata__, "chat_id") or ""),
            "message_id": str(
                self._metadata_value(body, __metadata__, "message_id") or ""
            ),
            "model": self._model_id(body, __model__),
            "prompt_label": str(self.valves.prompt_label),
            "forced_tool_ids": ",".join(self._parse_forced_tool_ids()),
            "forced_skill_ids": ",".join(self._parse_forced_skill_ids()),
            "passthrough": str(self._is_passthrough_model(body, __model__)).lower(),
        }

    def _trace_tags(self) -> list[str]:
        return list(TRACE_TAGS)

    def _user_identifier(self, __user__: Optional[dict]) -> str:
        """Prefer the email, fall back to the OpenWebUI user id."""
        if not __user__:
            return ""
        if isinstance(__user__, dict):
            value = __user__.get("email") or __user__.get("id") or ""
        else:
            value = getattr(__user__, "email", "") or getattr(__user__, "id", "")
        return str(value).strip()

    def _resolve_trace_ids(
        self, body: dict, __metadata__: Optional[dict], __chat_id__, __message_id__
    ) -> Optional[tuple]:
        """Return (chat_id, message_id) for traceable requests, else None."""
        chat_id = str(
            __chat_id__ or self._metadata_value(body, __metadata__, "chat_id") or ""
        ).strip()
        message_id = str(
            __message_id__
            or self._metadata_value(body, __metadata__, "message_id")
            or ""
        ).strip()
        if not chat_id or not message_id:
            return None
        # Temporary chats (chat_id "local:<socket>") are not persisted by
        # OpenWebUI; honor that and do not trace them either.
        if chat_id.startswith("local:"):
            return None
        return chat_id, message_id

    def _trace_attributes(
        self,
        body: dict,
        __user__: Optional[dict],
        __metadata__: Optional[dict],
        __model__,
        chat_id: str,
        message_id: str,
    ) -> dict:
        """Trace-wide attributes, copied on every span (Langfuse v4 queries
        observations directly, root-only attributes are not filterable)."""
        attributes = {
            "langfuse.trace.name": TRACE_NAME,
            "langfuse.session.id": chat_id,
            "langfuse.trace.tags": self._trace_tags(),
        }
        user = self._user_identifier(__user__)
        if user:
            attributes["langfuse.user.id"] = user
        metadata = {
            **self._trace_metadata(body, __metadata__, __model__),
            "chat_id": chat_id,
            "message_id": message_id,
            "owui_trace_key": self._trace_seed(chat_id, message_id),
        }
        for key, value in metadata.items():
            attributes[f"langfuse.trace.metadata.{key}"] = value
        return attributes

    def _remember_start(self, seed: str, start_ns: int) -> None:
        self._inflight_starts[seed] = start_ns
        self._inflight_starts.move_to_end(seed)
        while len(self._inflight_starts) > INFLIGHT_LIMIT:
            self._inflight_starts.popitem(last=False)

    def _pop_start(self, seed: str) -> Optional[int]:
        return self._inflight_starts.pop(seed, None)

    def _otlp_value(self, value) -> dict:
        if isinstance(value, bool):
            return {"boolValue": value}
        if isinstance(value, int):
            return {"intValue": str(value)}
        if isinstance(value, float):
            return {"doubleValue": value}
        if isinstance(value, (list, tuple)):
            return {"arrayValue": {"values": [self._otlp_value(v) for v in value]}}
        return {"stringValue": str(value)}

    def _otlp_attributes(self, attributes: dict) -> list:
        return [
            {"key": key, "value": self._otlp_value(value)}
            for key, value in attributes.items()
            if value is not None and value != ""
        ]

    def _otlp_span(
        self,
        *,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str],
        name: str,
        start_ns: int,
        end_ns: int,
        attributes: dict,
    ) -> dict:
        span = {
            "traceId": trace_id,
            "spanId": span_id,
            "name": name,
            "kind": 1,  # SPAN_KIND_INTERNAL
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": self._otlp_attributes(attributes),
            "status": {"code": 1},  # STATUS_CODE_OK
        }
        if parent_span_id:
            span["parentSpanId"] = parent_span_id
        return span

    def _otlp_payload(self, spans: list) -> dict:
        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": self._otlp_attributes(
                            {"service.name": "openwebui"}
                        )
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "openwebuitools.system"},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

    def _json_attribute(self, value) -> str:
        return json.dumps(value, ensure_ascii=False)

    async def _ensure_clock_offset(self, client) -> None:
        """Calibrate against the Langfuse server clock once per process.

        Langfuse uses the client-provided span timestamps as observation times;
        a skewed container clock misorders traces and breaks time filters.
        """
        if self._clock_offset is not None:
            return
        try:
            from datetime import datetime, timezone
            from email.utils import parsedate_to_datetime

            response = await client.get(
                f"{self.valves.langfuse_host.rstrip('/')}/api/public/health"
            )
            server_now = parsedate_to_datetime(response.headers["date"])
            offset = (server_now - datetime.now(timezone.utc)).total_seconds()
            if abs(offset) > 30:
                log.warning(
                    "Local clock differs from Langfuse server by %.0fs; "
                    "correcting trace timestamps.",
                    offset,
                )
            self._clock_offset = offset
        except Exception as exc:
            log.warning("Langfuse clock calibration failed: %s", exc)
            self._clock_offset = 0.0

    def _shift_span_times(self, spans: list) -> None:
        # Only correct a real skew: the server Date header has a 1 s resolution.
        offset = self._clock_offset or 0.0
        if abs(offset) <= 30:
            return
        shift = int(offset * 1_000_000_000)
        for span in spans:
            for key in ("startTimeUnixNano", "endTimeUnixNano"):
                span[key] = str(int(span[key]) + shift)

    async def _post_otlp(self, spans: list) -> None:
        import httpx

        if not (self.valves.langfuse_public_key and self.valves.langfuse_secret_key):
            raise RuntimeError("Langfuse public and secret keys are required for tracing.")

        url = f"{self.valves.langfuse_host.rstrip('/')}/api/public/otel/v1/traces"
        auth = (self.valves.langfuse_public_key, self.valves.langfuse_secret_key)
        async with httpx.AsyncClient(timeout=10.0) as client:
            await self._ensure_clock_offset(client)
            self._shift_span_times(spans)
            response = await client.post(
                url,
                json=self._otlp_payload(spans),
                auth=auth,
                headers={"x-langfuse-ingestion-version": "4"},
            )
        if response.status_code not in (200, 202):
            raise RuntimeError(
                f"Langfuse OTLP export failed ({response.status_code}): {response.text[:500]}"
            )
        try:
            partial = (response.json() or {}).get("partialSuccess") or {}
        except ValueError:
            partial = {}
        rejected = int(partial.get("rejectedSpans") or 0)
        if rejected:
            raise RuntimeError(
                f"Langfuse rejected {rejected} span(s): {partial.get('errorMessage', '')}"
            )

    def _spawn_export(self, spans: list) -> None:
        """Fire-and-forget so tracing never delays or breaks a chat request."""
        import asyncio

        async def _run():
            try:
                await self._post_otlp(spans)
            except Exception as exc:
                log.error("Langfuse trace export failed: %s", exc)

        task = asyncio.create_task(_run())
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    def _record_request_trace(
        self,
        body: dict,
        __user__: Optional[dict],
        __metadata__: Optional[dict],
        __chat_id__,
        __message_id__,
        __model__,
    ) -> None:
        """Export the request event at inlet time so failed messages are traced."""
        ids = self._resolve_trace_ids(body, __metadata__, __chat_id__, __message_id__)
        if ids is None:
            return
        chat_id, message_id = ids
        start_ns = time.time_ns()
        self._remember_start(self._trace_seed(chat_id, message_id), start_ns)

        attributes = {
            **self._trace_attributes(
                body, __user__, __metadata__, __model__, chat_id, message_id
            ),
            "langfuse.observation.type": "event",
            "langfuse.observation.input": self._json_attribute(
                {"last_user_message": self._last_message_content(body, "user")}
            ),
            "langfuse.observation.metadata.status": "pending",
        }
        span = self._otlp_span(
            trace_id=self._build_trace_id(chat_id, message_id),
            span_id=self._request_observation_id(chat_id, message_id),
            # The root span is exported at outlet time with a deterministic id;
            # Langfuse attaches this event to it once it arrives.
            parent_span_id=self._root_observation_id(chat_id, message_id),
            name=REQUEST_EVENT_NAME,
            start_ns=start_ns,
            end_ns=start_ns,
            attributes=attributes,
        )
        self._spawn_export([span])

    def _dedupe_ids(self, ids) -> list[str]:
        result = []
        seen = set()
        for id_ in ids:
            value = str(id_).strip() if id_ is not None else ""
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _dedupe_tool_ids(self, tool_ids) -> list[str]:
        return self._dedupe_ids(tool_ids)

    def _parse_forced_tool_ids(self) -> list[str]:
        raw = str(self.valves.forced_tool_ids or "")
        return self._dedupe_ids(raw.replace("\n", ",").split(","))

    def _parse_forced_skill_ids(self) -> list[str]:
        raw = str(self.valves.forced_skill_ids or "")
        return self._dedupe_ids(raw.replace("\n", ",").split(","))

    def _coerce_ids(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return self._dedupe_ids([value])
        if isinstance(value, (list, tuple, set)):
            return self._dedupe_ids(value)
        return []

    def _coerce_tool_ids(self, value) -> list[str]:
        return self._coerce_ids(value)

    def _coerce_skill_ids(self, value) -> list[str]:
        return self._coerce_ids(value)

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

    def _get_user_id(self, __user__: Optional[dict]) -> str:
        if not __user__:
            return ""
        if isinstance(__user__, dict):
            return str(__user__.get("id", "") or "").strip()
        return str(getattr(__user__, "id", "") or "").strip()

    async def _get_unresolved_forced_skill_ids(
        self, forced_skill_ids: list[str], __user__: Optional[dict] = None
    ) -> list[str]:
        if not forced_skill_ids:
            return []

        try:
            from open_webui.models.skills import Skills

            user_id = self._get_user_id(__user__)
            accessible_skill_ids = set(forced_skill_ids)
            if user_id:
                if hasattr(Skills, "get_skills"):
                    # Open WebUI >= 0.11: get_skills filters by read access.
                    accessible_skills = await Skills.get_skills(
                        user_id=user_id, ids=forced_skill_ids
                    )
                else:
                    accessible_skills = await Skills.get_skills_by_user_id(
                        user_id, "read"
                    )
                accessible_skill_ids = {
                    str(skill.id).strip()
                    for skill in accessible_skills or []
                    if getattr(skill, "id", None)
                }

            unresolved_skill_ids = []
            for skill_id in forced_skill_ids:
                if skill_id not in accessible_skill_ids:
                    unresolved_skill_ids.append(skill_id)
                    continue

                skill = await Skills.get_skill_by_id(skill_id)
                if not skill or not getattr(skill, "is_active", False):
                    unresolved_skill_ids.append(skill_id)

            return unresolved_skill_ids
        except ImportError:
            return []
        except Exception as exc:
            log.warning("Could not validate forced skill_ids: %s", exc)
            return []

    def _log_unresolved_forced_skill_ids(self, unresolved_skill_ids: list[str]) -> None:
        new_unresolved = [
            skill_id
            for skill_id in unresolved_skill_ids
            if skill_id not in self._warned_unresolved_skill_ids
        ]
        if not new_unresolved:
            return

        self._warned_unresolved_skill_ids.update(new_unresolved)
        log.warning(
            "Forced skill_ids could not be resolved, are inactive, "
            "or may be inaccessible and may be ignored: %s",
            ", ".join(new_unresolved),
        )

    async def _force_tool_ids(self, body: dict, __request__=None) -> None:
        forced_tool_ids = self._parse_forced_tool_ids()
        if not forced_tool_ids:
            return

        body["tool_ids"] = self._dedupe_ids(
            [*self._coerce_tool_ids(body.get("tool_ids")), *forced_tool_ids]
        )

        unresolved_tool_ids = await self._get_unresolved_forced_tool_ids(
            forced_tool_ids, __request__
        )
        self._log_unresolved_forced_tool_ids(unresolved_tool_ids)

    async def _force_skill_ids(
        self, body: dict, __user__: Optional[dict] = None
    ) -> None:
        forced_skill_ids = self._parse_forced_skill_ids()
        if not forced_skill_ids:
            return

        body["skill_ids"] = self._dedupe_ids(
            [*self._coerce_skill_ids(body.get("skill_ids")), *forced_skill_ids]
        )

        unresolved_skill_ids = await self._get_unresolved_forced_skill_ids(
            forced_skill_ids, __user__
        )
        self._log_unresolved_forced_skill_ids(unresolved_skill_ids)

    async def inlet(
        self,
        body: dict,
        __request__=None,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __chat_id__=None,
        __message_id__=None,
        __model__=None,
    ) -> dict:
        # Trace first: a failing prompt fetch (or any downstream error) must
        # still leave a trace with input, user and session in Langfuse.
        if self.valves.enable_tracing:
            try:
                self._record_request_trace(
                    body, __user__, __metadata__, __chat_id__, __message_id__, __model__
                )
            except Exception as exc:
                log.error("Langfuse request tracing failed: %s", exc)

        if self._is_passthrough_model(body, __model__):
            self._strip_owui_tooling(body)
            return body

        await self._force_tool_ids(body, __request__)
        await self._force_skill_ids(body, __user__)

        if not self.valves.enabled:
            return body

        injected_prompt = await self._build_injected_prompt(__user__)
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

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __chat_id__=None,
        __message_id__=None,
        __model__=None,
    ) -> None:
        if not self.valves.enable_tracing:
            return None

        chat_id = str(
            __chat_id__ or self._metadata_value(body, __metadata__, "chat_id") or ""
        ).strip()
        message_id = str(
            __message_id__
            or self._metadata_value(body, __metadata__, "message_id")
            or ""
        ).strip()
        if not chat_id or not message_id:
            log.warning(
                "Skipping Langfuse trace recording: missing chat_id or message_id."
            )
            return None
        if chat_id.startswith("local:"):
            return None

        try:
            end_ns = time.time_ns()
            start_ns = self._pop_start(self._trace_seed(chat_id, message_id)) or end_ns
            overall_input = self._json_attribute(
                {"last_user_message": self._last_message_content(body, "user")}
            )
            overall_output = self._json_attribute(
                {"assistant_message": self._last_message_content(body, "assistant")}
            )
            attributes = {
                **self._trace_attributes(
                    body, __user__, __metadata__, __model__, chat_id, message_id
                ),
                "langfuse.observation.type": "span",
                # Langfuse v4: the overall request and response live on the root
                # observation.
                "langfuse.observation.input": overall_input,
                "langfuse.observation.output": overall_output,
                "langfuse.observation.metadata.status": "completed",
                # Deprecated in v4, kept for trace-level evaluators such as
                # evals/owui_judge.py (run_batched_evaluation scope="traces").
                "langfuse.trace.input": overall_input,
                "langfuse.trace.output": overall_output,
            }
            span = self._otlp_span(
                trace_id=self._build_trace_id(chat_id, message_id),
                span_id=self._root_observation_id(chat_id, message_id),
                parent_span_id=None,
                name=TRACE_NAME,
                start_ns=start_ns,
                end_ns=end_ns,
                attributes=attributes,
            )
            self._spawn_export([span])
        except Exception as exc:
            log.error("Langfuse trace recording failed: %s", exc)

        return None
