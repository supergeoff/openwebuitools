"""
title: Moltis
author: supergeoff
version: 0.0.1
description: Connect to a Moltis GraphQL API with streaming via WebSocket subscriptions. Translates GraphQL chat events into Open WebUI streaming responses with real-time tool call status.
requirements: gql[all]
"""

import json
import asyncio
import ssl
import httpx
from typing import Optional
from pydantic import BaseModel, Field

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport


SEND_MUTATION = """
mutation SendMessage($message: String!, $sessionKey: String) {
    chatSend: chat.send(message: $message, sessionKey: $sessionKey) {
        ok
    }
}
"""

ABORT_MUTATION = """
mutation AbortSession($sessionKey: String) {
    chatAbort: chat.abort(sessionKey: $sessionKey) {
        ok
    }
}
"""

CHAT_EVENT_SUBSCRIPTION = gql(
    """
subscription OnChatEvent($sessionKey: String) {
    chatEvent(sessionKey: $sessionKey) {
        data
    }
}
"""
)


class Pipe:
    class Valves(BaseModel):
        model_display_name: str = Field(
            default="Moltis",
            description="Model name shown in the Open WebUI selector",
        )
        model_id: str = Field(
            default="moltis",
            description="Model slug used internally (lowercase, no spaces)",
        )

    class UserValves(BaseModel):
        moltis_graphql_url: str = Field(
            default="https://localhost:36531/graphql",
            description="Moltis GraphQL endpoint URL (used for both HTTP and WebSocket)",
        )
        moltis_api_key: str = Field(
            default="",
            description="Bearer token for Moltis authentication",
            json_schema_extra={"input": {"type": "password"}},
        )
        session_prefix: str = Field(
            default="openwebui",
            description="Session key prefix. Session will be '{prefix}:{user_id}'. Leave empty to use user_id only.",
        )
        show_thinking_status: bool = Field(
            default=True,
            description="Show 'Thinking...' status at start",
        )
        show_done_status: bool = Field(
            default=True,
            description="Show 'Done' status when response is complete",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "moltis"
        self.name = "Moltis: "
        self.valves = self.Valves()

    def pipes(self):
        return [
            {
                "id": self.valves.model_id,
                "name": self.valves.model_display_name,
            }
        ]

    def _get_user_valves(self, __user__: dict) -> dict:
        uv_raw = __user__.get("valves", {}) if __user__ else {}
        if hasattr(uv_raw, "__dict__") and not isinstance(uv_raw, dict):
            return uv_raw.__dict__
        return uv_raw if isinstance(uv_raw, dict) else {}

    def _build_session_key(self, session_prefix: str, user_id: str) -> str:
        prefix = session_prefix.strip()
        if prefix:
            return f"{prefix}:{user_id}"
        return user_id

    def _http_url(self, graphql_url: str) -> str:
        return graphql_url

    def _ws_url(self, graphql_url: str) -> str:
        return graphql_url.replace("https://", "wss://").replace("http://", "ws://")

    async def _gql_send(
        self, message: str, session_key: str, api_key: str, http_url: str
    ) -> bool:
        payload = {
            "query": SEND_MUTATION,
            "variables": {"message": message, "sessionKey": session_key},
        }
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0), verify=False
        ) as client:
            resp = await client.post(http_url, json=payload, headers=headers)
            if resp.status_code != 200:
                return False
            data = resp.json()
            return data.get("data", {}).get("chatSend", {}).get("ok", False)

    async def _gql_abort(
        self, session_key: str, api_key: str, http_url: str
    ) -> bool:
        payload = {
            "query": ABORT_MUTATION,
            "variables": {"sessionKey": session_key},
        }
        headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0), verify=False
            ) as client:
                resp = await client.post(http_url, json=payload, headers=headers)
                if resp.status_code != 200:
                    return False
                data = resp.json()
                return data.get("data", {}).get("chatAbort", {}).get("ok", False)
        except Exception:
            return False

    async def _subscribe_chat_events(
        self, session_key: str, ws_url: str, api_key: str
    ):
        init_payload = {}
        if api_key:
            init_payload["Authorization"] = f"Bearer {api_key}"

        ssl_context = None
        if ws_url.startswith("wss://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        transport = WebsocketsTransport(
            url=ws_url,
            init_payload=init_payload,
            ssl=ssl_context,
        )

        client = Client(transport=transport, fetch_schema_from_transport=False)

        try:
            async with client as session:
                async for result in session.subscribe(
                    CHAT_EVENT_SUBSCRIPTION,
                    variable_values={"sessionKey": session_key},
                ):
                    event_data = result.get("chatEvent", {}).get("data", {})
                    if not event_data:
                        continue
                    state = event_data.get("state", "")
                    yield ("event", state, event_data)
        except Exception as e:
            yield ("error", str(e), {})

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __request__,
        __event_emitter__: Optional[callable] = None,
    ):
        uv_dict = self._get_user_valves(__user__)
        defaults = self.UserValves()

        graphql_url = uv_dict.get("moltis_graphql_url", defaults.moltis_graphql_url)
        api_key = uv_dict.get("moltis_api_key", defaults.moltis_api_key)
        session_prefix = uv_dict.get("session_prefix", defaults.session_prefix)
        show_thinking = uv_dict.get(
            "show_thinking_status", defaults.show_thinking_status
        )
        show_done = uv_dict.get("show_done_status", defaults.show_done_status)

        if not api_key:
            yield "No API key configured. Set your moltis_api_key in User Valves."
            return

        user_id = __user__.get("id", "anonymous") if __user__ else "anonymous"
        session_key = self._build_session_key(session_prefix, user_id)

        messages = body.get("messages", [])
        if not messages:
            yield "No messages to send."
            return

        last_msg = messages[-1].get("content", "")
        if not last_msg:
            yield "Empty message."
            return

        http_url = self._http_url(graphql_url)
        ws_url = self._ws_url(graphql_url)

        if __event_emitter__ and show_thinking:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Thinking...", "done": False},
                }
            )

        send_ok = await self._gql_send(last_msg, session_key, api_key, http_url)
        if not send_ok:
            yield "Failed to send message to Moltis. Check your API key and GraphQL URL."
            return

        try:
            async for event_type, state, data in self._subscribe_chat_events(
                session_key, ws_url, api_key
            ):
                if event_type == "error":
                    yield f"Subscription error: {state}"
                    return

                if state == "delta":
                    text = data.get("text", "")
                    if text:
                        yield text

                elif state == "final":
                    tool_calls = data.get("toolCallsMade", 0)
                    if tool_calls > 0 and __event_emitter__:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {
                                    "description": f"Tools: {tool_calls} call(s) executed",
                                    "done": False,
                                },
                            }
                        )

                    if __event_emitter__ and show_done:
                        await __event_emitter__(
                            {
                                "type": "status",
                                "data": {"description": "Done", "done": True},
                            }
                        )
                    return

                elif state == "error":
                    error_text = data.get("text", "Unknown error")
                    yield f"Moltis error: {error_text}"
                    return

        except GeneratorExit:
            await self._gql_abort(session_key, api_key, http_url)
            return
        except asyncio.CancelledError:
            await self._gql_abort(session_key, api_key, http_url)
            return
        except httpx.ConnectError:
            yield "Cannot connect. Check moltis_graphql_url in your User Valves."
            return
        except httpx.TimeoutException:
            await self._gql_abort(session_key, api_key, http_url)
            yield "Request timed out."
            return
        except Exception as e:
            yield f"Unexpected error: {str(e)}"
            return
