'''
title: Moltis
author: supergeoff
version: 0.1.0
description: Connect to a Moltis GraphQL API with streaming via WebSocket subscriptions. Translates GraphQL chat events into Open WebUI streaming responses with real-time tool call status.
requirements: websockets
'''

import json
import asyncio
import ssl
import httpx
import websockets
from typing import Optional
from pydantic import BaseModel, Field


SEND_MUTATION = '''
mutation SendMessage($message: String!, $sessionKey: String) {
    chat {
        send(message: $message, sessionKey: $sessionKey) {
            ok
        }
    }
}
'''

ABORT_MUTATION = '''
mutation AbortSession($sessionKey: String) {
    chat {
        abort(sessionKey: $sessionKey) {
            ok
        }
    }
}
'''

CHAT_EVENT_SUBSCRIPTION = '''
subscription OnChatEvent($sessionKey: String) {
    chatEvent(sessionKey: $sessionKey) {
        data
    }
}
'''


class Pipe:
    class Valves(BaseModel):
        model_display_name: str = Field(
            default='Moltis',
            description='Model name shown in the Open WebUI selector',
        )
        model_id: str = Field(
            default='moltis',
            description='Model slug used internally (lowercase, no spaces)',
        )

    class UserValves(BaseModel):
        moltis_graphql_url: str = Field(
            default='https://moltis-production-756e.up.railway.app/graphql',
            description='Moltis GraphQL endpoint URL (used for both HTTP and WebSocket)',
        )
        moltis_api_key: str = Field(
            default='',
            description='Bearer token for Moltis authentication',
            json_schema_extra={'input': {'type': 'password'}},
        )
        session_suffix: str = Field(
            default='',
            description='Session suffix (leave empty to use user_id). Session will be openwebui:suffix',
        )
        show_thinking_status: bool = Field(
            default=True,
            description='Show Thinking... status at start',
        )
        show_done_status: bool = Field(
            default=True,
            description='Show Done status when response is complete',
        )

    def __init__(self):
        self.type = 'manifold'
        self.id = 'moltis'
        self.name = 'Moltis: '
        self.valves = self.Valves()

    def pipes(self):
        return [
            {
                'id': self.valves.model_id,
                'name': self.valves.model_display_name,
            }
        ]

    def _get_user_valves(self, __user__: dict) -> dict:
        uv_raw = __user__.get('valves', {}) if __user__ else {}
        if hasattr(uv_raw, '__dict__') and not isinstance(uv_raw, dict):
            return uv_raw.__dict__
        return uv_raw if isinstance(uv_raw, dict) else {}

    def _build_session_key(self, session_suffix: str, user_id: str) -> str:
        suffix = session_suffix.strip() if session_suffix else user_id
        return f'openwebui:{suffix}'

    def _http_url(self, graphql_url: str) -> str:
        return graphql_url

    def _ws_url(self, graphql_url: str) -> str:
        return graphql_url.replace('https://', 'wss://').replace('http://', 'ws://')

    def _ws_headers(self, api_key: str) -> list[tuple[str, str]]:
        headers = []
        if api_key:
            headers.append(('Authorization', f'Bearer {api_key}'))
        return headers

    def _ws_ssl_context(self) -> Optional[ssl.SSLContext]:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def _gql_send(
        self, message: str, session_key: str, api_key: str, http_url: str
    ) -> tuple[bool, str]:
        query = f'mutation SendMessage {{ chat {{ send(message: """{message}""", sessionKey: "{session_key}") {{ ok }} }} }}'
        payload = {
            'query': query,
        }
        headers = {
            'Content-Type': 'application/json',
        }
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        else:
            return False, 'No API key provided'

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=False,
            follow_redirects=True,
        ) as client:
            resp = await client.post(http_url, json=payload, headers=headers)
            raw_body = resp.text
            if resp.status_code != 200:
                preview = raw_body[:500] if raw_body else '(empty body)'
                return False, f'HTTP {resp.status_code}: {preview}'
            try:
                data = resp.json()
            except Exception:
                return False, f'Non-JSON response (HTTP {resp.status_code}): {raw_body[:500] or "(empty body)"}'
            errors = data.get('errors')
            if errors:
                return False, f'GraphQL error: {errors[0].get("message", str(errors))}'
            ok = data.get('data', {}).get('chat', {}).get('send', {}).get('ok')
            if ok is None:
                return False, 'Unexpected response format from Moltis'
            return ok, ''

    async def _gql_abort(
        self, session_key: str, api_key: str, http_url: str
    ) -> bool:
        payload = {
            'query': ABORT_MUTATION,
            'variables': {'sessionKey': session_key},
        }
        headers = {
            'Content-Type': 'application/json',
        }
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                verify=False,
                follow_redirects=True,
            ) as client:
                resp = await client.post(http_url, json=payload, headers=headers)
                if resp.status_code != 200:
                    return False
                try:
                    data = resp.json()
                except Exception:
                    return False
                ok = data.get('data', {}).get('chat', {}).get('abort', {}).get('ok')
                return ok is True
        except Exception:
            return False

    async def _subscribe_chat_events(
        self, session_key: str, ws_url: str, api_key: str
    ):
        ssl_ctx = self._ws_ssl_context()
        headers = self._ws_headers(api_key)

        try:
            async with websockets.connect(
                ws_url,
                ssl=ssl_ctx,
                additional_headers=headers,
                subprotocols=['graphql-transport-ws'],
                open_timeout=10,
                close_timeout=5,
            ) as ws:
                init_msg = json.dumps({'type': 'connection_init', 'payload': {}})
                await ws.send(init_msg)
                ack = await asyncio.wait_for(ws.recv(), timeout=10)
                ack_data = json.loads(ack)
                if ack_data.get('type') != 'connection_ack':
                    yield ('error', f'Unexpected init response: {ack}', {})
                    return

                sub_msg = json.dumps({
                    'id': 'sub1',
                    'type': 'subscribe',
                    'payload': {
                        'query': CHAT_EVENT_SUBSCRIPTION,
                        'variables': {'sessionKey': session_key},
                    },
                })
                await ws.send(sub_msg)

                async for raw_msg in ws:
                    try:
                        parsed = json.loads(raw_msg)
                    except json.JSONDecodeError:
                        continue

                    msg_type = parsed.get('type', '')

                    if msg_type == 'next':
                        event_data = (
                            parsed.get('payload', {})
                            .get('data', {})
                            .get('chatEvent', {})
                            .get('data', {})
                        )
                        if not event_data:
                            continue
                        state = event_data.get('state', '')
                        yield ('event', state, event_data)
                        if state == 'final':
                            break

                    elif msg_type == 'error':
                        yield ('error', f'Subscription error: {parsed}', {})
                        return

                    elif msg_type == 'complete':
                        return

        except websockets.exceptions.ConnectionClosed as e:
            yield ('error', f'WebSocket closed: {e.code} {e.reason}', {})
        except asyncio.TimeoutError:
            yield ('error', 'WebSocket connection timeout', {})
        except Exception as e:
            yield ('error', f'WebSocket error: {type(e).__name__}: {e}', {})

    async def pipe(
        self,
        body: dict,
        __user__: dict,
        __request__,
        __event_emitter__: Optional[callable] = None,
    ):
        uv_dict = self._get_user_valves(__user__)
        defaults = self.UserValves()

        graphql_url = uv_dict.get('moltis_graphql_url', defaults.moltis_graphql_url)
        api_key = uv_dict.get('moltis_api_key', defaults.moltis_api_key)
        session_suffix = uv_dict.get('session_suffix', defaults.session_suffix)
        show_thinking = uv_dict.get(
            'show_thinking_status', defaults.show_thinking_status
        )
        show_done = uv_dict.get('show_done_status', defaults.show_done_status)

        user_id = __user__.get('id', 'anonymous') if __user__ else 'anonymous'
        session_key = self._build_session_key(session_suffix, user_id)

        if not api_key or len(api_key) < 10:
            yield 'No API key configured. Set your moltis_api_key in User Valves.'
            return

        messages = body.get('messages', [])
        if not messages:
            yield 'No messages to send.'
            return

        last_msg = messages[-1].get('content', '')
        if not last_msg:
            yield 'Empty message.'
            return

        http_url = self._http_url(graphql_url)
        ws_url = self._ws_url(graphql_url)

        if __event_emitter__ and show_thinking:
            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {'description': 'Thinking...', 'done': False},
                }
            )

        try:
            send_ok, error_msg = await self._gql_send(
                last_msg, session_key, api_key, http_url
            )
        except Exception as e:
            yield f'[ERROR in _gql_send] {type(e).__name__}: {e}'
            return

        if not send_ok:
            yield f'Failed to send message to Moltis: {error_msg}'
            return

        try:
            async for event_type, state, data in self._subscribe_chat_events(
                session_key, ws_url, api_key
            ):
                if event_type == 'error':
                    yield f'Subscription error: {state}'
                    return

                if state == 'delta':
                    text = data.get('text', '')
                    if text:
                        yield text

                elif state == 'final':
                    tool_calls = data.get('toolCallsMade', 0)
                    if tool_calls > 0 and __event_emitter__:
                        await __event_emitter__(
                            {
                                'type': 'status',
                                'data': {
                                    'description': f'Tools: {tool_calls} call(s) executed',
                                    'done': False,
                                },
                            }
                        )

                    if __event_emitter__ and show_done:
                        await __event_emitter__(
                            {
                                'type': 'status',
                                'data': {'description': 'Done', 'done': True},
                            }
                        )
                    return

                elif state == 'error':
                    error_text = data.get('text', 'Unknown error')
                    yield f'Moltis error: {error_text}'
                    return

        except GeneratorExit:
            await self._gql_abort(session_key, api_key, http_url)
            return
        except asyncio.CancelledError:
            await self._gql_abort(session_key, api_key, http_url)
            return
        except httpx.ConnectError:
            yield 'Cannot connect. Check moltis_graphql_url in your User Valves.'
            return
        except httpx.TimeoutException:
            await self._gql_abort(session_key, api_key, http_url)
            yield 'Request timed out.'
            return
        except Exception as e:
            yield f'Unexpected error: {str(e)}'
            return