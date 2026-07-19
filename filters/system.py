"""
title: system
author: geoff
requirements: langfuse
description: >
  Single source of truth for the system prompt across ALL models.
  The prompt itself lives in Langfuse as multiple text prompt modules, fetched
  in order and injected as the system message on every request. The only
  per-user runtime value managed here is hindsight_bankid, exposed to the
  memory prompt as {{hindsight_bankid}}.
  Also records one Langfuse trace per assistant message with the deterministic
  id "owui-{chat_id}-{message_id}" (Langfuse ingestion API): created at inlet
  time (so failed requests still leave a trace with input, user and session),
  completed at outlet time with the assistant output. The LiteLLM generation
  joins the same trace when the OpenWebUI connection to LiteLLM sends the
  custom header "langfuse_existing_trace_id: owui-{{CHAT_ID}}-{{MESSAGE_ID}}".
  The langfuse_feedback action attaches its scores with the same id scheme.
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

log = logging.getLogger("global_policy_filter")

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
            default=300,
            description="Langfuse SDK cache TTL. Edits propagate after this delay.",
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

    def _fetch_policy(self, __user__: Optional[dict]) -> str:
        sections = []
        for prompt_name in self._prompt_module_names():
            variables = self._prompt_variables(prompt_name, __user__)
            text = self._fetch_prompt_module(prompt_name, variables)
            sections.append(f"# Prompt Module: {prompt_name}\n\n{text}")
        return "\n\n".join(sections)

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

    def _build_injected_prompt(
        self,
        __user__: Optional[dict],
    ) -> str:
        return self._fetch_policy(__user__).strip()

    def _build_trace_id(self, chat_id: str, message_id: str) -> str:
        # Deterministic id shared with the langfuse_feedback action and with
        # LiteLLM (OpenWebUI connection header langfuse_existing_trace_id).
        # Plain string on purpose: header templating cannot hash, and the
        # Langfuse ingestion API accepts arbitrary string trace ids.
        return f"owui-{chat_id}-{message_id}"

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

    def _ingestion_event(self, event_type: str, body: dict) -> dict:
        import uuid

        # Timestamps are stamped in _post_ingestion after clock calibration.
        return {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "body": body,
        }

    async def _ensure_clock_offset(self, client) -> None:
        """Calibrate against the Langfuse server clock once per process.

        Langfuse uses the client-provided event timestamps as trace/observation
        times; a skewed container clock breaks the trace/observation time join
        and misorders traces relative to LiteLLM generations.
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

    def _corrected_now_iso(self) -> str:
        from datetime import datetime, timedelta, timezone

        offset = self._clock_offset or 0.0
        return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat()

    async def _post_ingestion(self, events: list) -> None:
        import httpx

        if not (self.valves.langfuse_public_key and self.valves.langfuse_secret_key):
            raise RuntimeError("Langfuse public and secret keys are required for tracing.")

        url = f"{self.valves.langfuse_host.rstrip('/')}/api/public/ingestion"
        auth = (self.valves.langfuse_public_key, self.valves.langfuse_secret_key)
        async with httpx.AsyncClient(timeout=10.0) as client:
            await self._ensure_clock_offset(client)
            now = self._corrected_now_iso()
            for event in events:
                event.setdefault("timestamp", now)
                if event.get("type") == "event-create":
                    event["body"].setdefault("startTime", now)
            response = await client.post(url, json={"batch": events}, auth=auth)
        if response.status_code not in (200, 201, 207):
            raise RuntimeError(
                f"Langfuse ingestion failed ({response.status_code}): {response.text[:500]}"
            )
        errors = (response.json() or {}).get("errors") or []
        if errors:
            raise RuntimeError(f"Langfuse ingestion rejected events: {errors}")

    def _spawn_ingestion(self, events: list) -> None:
        """Fire-and-forget so tracing never delays or breaks a chat request."""
        import asyncio

        async def _run():
            try:
                await self._post_ingestion(events)
            except Exception as exc:
                log.error("Langfuse trace ingestion failed: %s", exc)

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
        """Create the trace at request time so failed messages are traced too."""
        chat_id = str(
            __chat_id__ or self._metadata_value(body, __metadata__, "chat_id") or ""
        ).strip()
        message_id = str(
            __message_id__
            or self._metadata_value(body, __metadata__, "message_id")
            or ""
        ).strip()
        if not chat_id or not message_id:
            return

        trace_id = self._build_trace_id(chat_id, message_id)
        event = self._ingestion_event(
            "trace-create",
            {
                "id": trace_id,
                "name": "owui-chat",
                "userId": self._user_identifier(__user__),
                "sessionId": chat_id,
                "tags": self._trace_tags(),
                "input": {"last_user_message": self._last_message_content(body, "user")},
                "metadata": {
                    **self._trace_metadata(body, __metadata__, __model__),
                    "status": "pending",
                },
            },
        )
        self._spawn_ingestion([event])

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
                accessible_skills = await Skills.get_skills_by_user_id(user_id, "read")
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

        await self._force_tool_ids(body, __request__)
        await self._force_skill_ids(body, __user__)

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

        try:
            metadata = self._trace_metadata(body, __metadata__, __model__)
            trace_id = self._build_trace_id(chat_id, message_id)
            assistant_message = self._last_message_content(body, "assistant")
            events = [
                # Complete the trace created at inlet time (upsert by id).
                # userId/sessionId/tags are repeated so the trace stays whole
                # even if the inlet event was lost.
                self._ingestion_event(
                    "trace-create",
                    {
                        "id": trace_id,
                        "name": "owui-chat",
                        "userId": self._user_identifier(__user__),
                        "sessionId": chat_id,
                        "tags": self._trace_tags(),
                        "output": {"assistant_message": assistant_message},
                        "metadata": {**metadata, "status": "completed"},
                    },
                ),
                self._ingestion_event(
                    "event-create",
                    {
                        "id": f"owui-evt-{chat_id}-{message_id}",
                        "traceId": trace_id,
                        "name": "owui-chat-response",
                        "input": {
                            "last_user_message": self._last_message_content(
                                body, "user"
                            )
                        },
                        "output": {"assistant_message": assistant_message},
                        "metadata": metadata,
                    },
                ),
            ]
            await self._post_ingestion(events)
        except Exception as exc:
            log.error("Langfuse trace recording failed: %s", exc)

        return None
