"""
title: Nous
author: supergeoff
version: 0.0.1
description: Proxy chat requests to a Hermes Agent API with real-time tool progress visualization. Translates SSE tool progress events into Open WebUI status indicators for live feedback during agent execution.
"""

import json
import httpx
from typing import Optional
from pydantic import BaseModel, Field


class Pipe:
    class Valves(BaseModel):
        model_display_name: str = Field(
            default="Hermes",
            description="Model name shown in the Open WebUI selector",
        )
        model_id: str = Field(
            default="hermes",
            description="Model slug used internally (lowercase, no spaces)",
        )

    class UserValves(BaseModel):
        hermes_base_url: str = Field(
            default="https://hermes-production-9f47.up.railway.app/v1",
            description="Hermes API base URL (must end with /v1)",
        )
        hermes_api_key: str = Field(
            default="",
            description="Your personal Hermes API key",
            json_schema_extra={"input": {"type": "password"}},
        )
        hermes_model: str = Field(
            default="hermes-agent",
            description="Model name on the Hermes API side",
        )
        show_thinking_status: bool = Field(
            default=True,
            description="Show 'Hermes is thinking...' status at start",
        )
        show_done_status: bool = Field(
            default=True,
            description="Show 'Done' status when response is complete",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "nous"
        self.name = "Nous: "
        self.valves = self.Valves()

    def pipes(self):
        return [
            {
                "id": self.valves.model_id,
                "name": self.valves.model_display_name,
            }
        ]

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __request__,
        __event_emitter__: Optional[callable] = None,
    ) -> Optional[str]:
        uv_raw = __user__.get("valves", {}) if __user__ else {}
        if hasattr(uv_raw, "__dict__") and not isinstance(uv_raw, dict):
            uv_dict = uv_raw.__dict__
        else:
            uv_dict = uv_raw if isinstance(uv_raw, dict) else {}

        defaults = self.UserValves()
        base_url = uv_dict.get("hermes_base_url", defaults.hermes_base_url)
        api_key = uv_dict.get("hermes_api_key", defaults.hermes_api_key)
        hermes_model = uv_dict.get("hermes_model", defaults.hermes_model)
        show_thinking = uv_dict.get(
            "show_thinking_status", defaults.show_thinking_status
        )
        show_done = uv_dict.get("show_done_status", defaults.show_done_status)

        if not api_key:
            yield "No API key configured. Set your hermes_api_key in User Valves."
            return

        messages = body.get("messages", [])
        model_id = body.get("model", self.valves.model_id)

        if "." in model_id:
            model_id = model_id.split(".")[-1]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": hermes_model,
            "messages": messages,
            "stream": body.get("stream", False),
        }

        if __event_emitter__ and show_thinking:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Thinking...",
                        "done": False,
                    },
                }
            )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0)
            ) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_body = await response.aread()
                        yield (
                            f"Error (HTTP {response.status_code}): "
                            f"{error_body.decode('utf-8', errors='replace')[:500]}"
                        )
                        return

                    current_event = None

                    async for line in response.aiter_lines():
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line[6:].strip()
                            continue

                        if not line.startswith("data:"):
                            continue

                        data_str = line[5:].strip()

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        if current_event == "hermes.tool.progress":
                            tool_name = data.get("tool", "")
                            emoji = data.get("emoji", "🔧")
                            label = data.get("label", tool_name)

                            if __event_emitter__:
                                await __event_emitter__(
                                    {
                                        "type": "status",
                                        "data": {
                                            "description": f"{label}...",
                                            "done": False,
                                        },
                                    }
                                )
                            current_event = None
                            continue

                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content

                        current_event = None

        except httpx.ConnectError:
            yield "Cannot connect. Check hermes_base_url in your User Valves."
            return
        except httpx.TimeoutException:
            yield "Request timed out."
            return
        except Exception as e:
            yield f"Unexpected error: {str(e)}"
            return

        if __event_emitter__ and show_done:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Done",
                        "done": True,
                    },
                }
            )
