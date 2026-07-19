"""
title: Langfuse Feedback
author: geoff
description: >
  Send explicit OpenWebUI message feedback to Langfuse scores via the public
  scores API. Scores attach to the deterministic trace id
  "owui-{chat_id}-{message_id}" shared with the system filter.
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field


log = logging.getLogger("langfuse_feedback_action")


ICON_BASE_URL = "https://cdn.jsdelivr.net/npm/lucide-static@0.468.0/icons"


class Action:
    actions = [
        {
            "id": "positive",
            "name": "Positive",
            "icon_url": f"{ICON_BASE_URL}/smile.svg",
        },
        {
            "id": "negative",
            "name": "Negative",
            "icon_url": f"{ICON_BASE_URL}/frown.svg",
        },
        {
            "id": "prompt_issue",
            "name": "Prompt issue",
            "icon_url": f"{ICON_BASE_URL}/message-circle-warning.svg",
        },
        {
            "id": "tool_issue",
            "name": "Tool issue",
            "icon_url": f"{ICON_BASE_URL}/wrench.svg",
        },
        {
            "id": "memory_issue",
            "name": "Memory issue",
            "icon_url": f"{ICON_BASE_URL}/brain.svg",
        },
    ]

    class Valves(BaseModel):
        priority: int = Field(default=0, description="Action button priority.")
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

    def __init__(self):
        self.valves = self.Valves()

    def _metadata_value(
        self, body: dict, __metadata__: Optional[dict], key: str, *body_aliases: str
    ):
        if __metadata__ and __metadata__.get(key) is not None:
            return __metadata__.get(key)
        metadata = body.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get(key) is not None:
            return metadata.get(key)
        for alias in body_aliases:
            if body.get(alias) is not None:
                return body.get(alias)
        return body.get(key)

    def _build_trace_id(self, chat_id: str, message_id: str) -> str:
        # Must stay identical to Filter._build_trace_id in filters/system.py.
        return f"owui-{chat_id}-{message_id}"

    def _user_id(self, __user__: Optional[dict]) -> str:
        if not __user__:
            return ""
        if isinstance(__user__, dict):
            return str(__user__.get("id", "") or "").strip()
        return str(getattr(__user__, "id", "") or "").strip()

    async def _notify(self, __event_emitter__, type_: str, content: str) -> None:
        if not __event_emitter__:
            return
        await __event_emitter__(
            {
                "type": "notification",
                "data": {"type": type_, "content": content},
            }
        )

    async def _collect_comment(self, feedback_type: str, __event_call__) -> str:
        if feedback_type == "positive" or not __event_call__:
            return ""
        result = await __event_call__(
            {
                "type": "input",
                "data": {
                    "title": "Langfuse feedback",
                    "message": "Commentaire pour qualifier ce feedback.",
                    "placeholder": "Ce qui devrait etre corrige...",
                },
            }
        )
        if isinstance(result, dict):
            return str(result.get("value", "") or result.get("comment", "") or "")
        return str(result or "")

    def _score_id(self, trace_id: str, user_id: str, name: str, feedback_type: str) -> str:
        return f"owui:{name}:{feedback_type}:{trace_id}:{user_id}"

    def _model_id(self, body: dict) -> str:
        return str(body.get("model", "") or "")

    async def _post_score(
        self,
        *,
        score_id: str,
        trace_id: str,
        name: str,
        value,
        data_type: str,
        comment: str,
        metadata: dict,
    ) -> None:
        import httpx

        if not (self.valves.langfuse_public_key and self.valves.langfuse_secret_key):
            raise RuntimeError("Langfuse public and secret keys are required.")

        payload = {
            "id": score_id,
            "traceId": trace_id,
            "name": name,
            "value": value,
            "dataType": data_type,
            "metadata": metadata,
        }
        if comment:
            payload["comment"] = comment

        url = f"{self.valves.langfuse_host.rstrip('/')}/api/public/scores"
        auth = (self.valves.langfuse_public_key, self.valves.langfuse_secret_key)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, auth=auth)
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Langfuse score creation failed ({response.status_code}): "
                f"{response.text[:500]}"
            )

    async def action(
        self,
        body: dict,
        __id__=None,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
        __chat_id__=None,
        __message_id__=None,
        __event_emitter__=None,
        __event_call__=None,
        **kwargs,
    ):
        feedback_type = str(__id__ or "").strip()
        valid_feedback_types = {item["id"] for item in self.actions}
        if feedback_type not in valid_feedback_types:
            await self._notify(
                __event_emitter__,
                "error",
                f"Unknown Langfuse feedback action: {feedback_type or 'missing'}.",
            )
            return None

        chat_id = str(
            __chat_id__ or self._metadata_value(body, __metadata__, "chat_id") or ""
        ).strip()
        message_id = str(
            __message_id__
            or self._metadata_value(body, __metadata__, "message_id", "id")
            or ""
        ).strip()
        if not chat_id or not message_id:
            await self._notify(
                __event_emitter__,
                "error",
                "Missing chat_id or message_id, Langfuse feedback was not sent.",
            )
            return None

        user_id = self._user_id(__user__)
        trace_id = self._build_trace_id(chat_id, message_id)
        comment = await self._collect_comment(feedback_type, __event_call__)
        feedback_value = 1.0 if feedback_type == "positive" else 0.0
        metadata = {
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": user_id,
            "model": self._model_id(body),
        }

        try:
            await self._post_score(
                score_id=self._score_id(
                    trace_id, user_id, "owui_user_feedback", feedback_type
                ),
                trace_id=trace_id,
                name="owui_user_feedback",
                value=feedback_value,
                data_type="NUMERIC",
                comment=comment,
                metadata=metadata,
            )
            await self._post_score(
                score_id=self._score_id(
                    trace_id, user_id, "owui_feedback_category", feedback_type
                ),
                trace_id=trace_id,
                name="owui_feedback_category",
                value=feedback_type,
                data_type="CATEGORICAL",
                comment=comment,
                metadata=metadata,
            )
        except Exception as exc:
            log.warning("Langfuse feedback failed: %s", exc)
            await self._notify(
                __event_emitter__,
                "error",
                f"Langfuse feedback failed: {exc}",
            )
            return None

        await self._notify(
            __event_emitter__,
            "success",
            "Langfuse feedback sent.",
        )
        return None
