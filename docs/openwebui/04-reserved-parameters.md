# Injected Parameters (Implicit API)

Open WebUI automatically injects certain parameters into extension functions. The mechanism uses `inspect.signature()` to match parameters declared by the function with available `extra_params`. Simply **declare the parameter in the signature** to receive it.

## Complete Reserved Parameters Reference

| Parameter | Type | Always Available | Description |
|-----------|------|---------------------|-------------|
| `body` | dict | Yes | Chat completion request dictionary: stream, model, messages, features, stream_options, metadata, files |
| `__user__` | dict | Yes | `{id, email, name, role ("user"|"admin"), valves (if UserValves defined)}` |
| `__metadata__` | dict | Yes | Enriched context metadata (see structure below) |
| `__model__` | dict | Yes | Complete model object (see structure below) |
| `__messages__` | list | Yes | List of messages, identical to `body["messages"]` |
| `__chat_id__` | str | Chat context | Unique UUID of the conversation |
| `__session_id__` | str | Usually | Session identifier |
| `__message_id__` | str | Chat context | Current message identifier |
| `__event_emitter__` | Callable | Function context | One-way communication to frontend |
| `__event_call__` | Callable | Function context | Bidirectional communication, 300s timeout (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`). Available in Tools, Actions, Pipes, and Filters. |
| `__files__` | list | Yes ([] if empty) | List of file objects (see structure below) |
| `__request__` | fastapi.Request | Yes | FastAPI Request instance |
| `__task__` | str | Task context | Internal task type |
| `__task_body__` | dict | Task context | Body specific to internal task |
| `__tools__` | list | Yes | List of ToolUserModel instances (see structure below) |
| `__id__` | str | Actions | Action identifier (useful for multi-actions) |
| `__oauth_token__` | dict | If configured | User OAuth token (auto-refreshed). Recommended method for authenticated API calls (see structure below) |

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args — consulted 04/13/2026

## `__metadata__` Structure

```python
{
    "user_id": "uuid",
    "chat_id": "uuid",
    "message_id": "uuid",
    "session_id": "string",
    "tool_ids": null|[list of str],
    "tool_servers": [],
    "files": "[Same as __files__]",
    "features": {
        "image_generation": False,
        "code_interpreter": False,
        "web_search": False
    },
    "variables": {
        "{{USER_NAME}}": "cheesy_username",
        "{{USER_LOCATION}}": "Unknown",
        "{{CURRENT_DATETIME}}": "2025-02-02 XX:XX:XX",
        "{{CURRENT_DATE}}": "2025-02-02",
        "{{CURRENT_TIME}}": "XX:XX:XX",
        "{{CURRENT_WEEKDAY}}": "Monday",
        "{{CURRENT_TIMEZONE}}": "Europe/Berlin",
        "{{USER_LANGUAGE}}": "en-US"
    },
    "model": "[Identical to __model__]",
    "direct": False,
    "function_calling": "native",
    "type": "user_response",
    "interface": "open-webui|other"
}
```

### Internal Task Types (`__task__`)

`title_generation`, `tags_generation`, `emoji_generation`, `query_generation`, `image_prompt_generation`, `autocomplete_generation`, `function_calling`, `moa_response_generation`

### Detecting Request Source

```python
if __metadata__ and __metadata__.get("interface") == "open-webui":
    # Request from web interface
else:
    # Direct API request
```

## `__model__` Structure

```python
{
    "id": "my-cool-model",
    "name": "Display Name",
    "object": "model",
    "created": 1746000000,
    "owned_by": "openai|ollama",
    "info": {
        "id": "my-cool-model",
        "user_id": "uuid",
        "base_model_id": "gpt-4o",
        "name": "My Cool Model",
        "params": {
            "system": "System prompt...",
            "function_calling": "native"
        },
        "meta": {
            "profile_image_url": "/static/favicon.png",
            "description": "Model description",
            "capabilities": {"vision": True, "usage": True, "citations": True},
            "position": 17,
            "tags": [{"name": "tag_name"}],
            "suggestion_prompts": None
        },
        "access_control": {
            "read": {"group_ids": [], "user_ids": []},
            "write": {"group_ids": [], "user_ids": []}
        },
        "is_active": True,
        "updated_at": 1740000000,
        "created_at": 1740000000
    },
    "preset": True,
    "actions": [],
    "tags": [{"name": "tag_name"}]
}
```

## `__files__` Structure

Images are excluded from `__files__` — they are sent as base64 directly in messages.

```python
[{
    "type": "file",
    "file": {
        "id": "uuid",
        "filename": "document.pdf",
        "user_id": "uuid",
        "hash": "hex_string",
        "data": {"content": "Parsed document content..."},
        "meta": {
            "name": "document.pdf",
            "content_type": "application/pdf",
            "size": 10486578,
            "data": {},
            "collection_name": "file-96xxxxxx..."
        },
        "created_at": 1740000000,
        "updated_at": 1740000000
    },
    "id": "uuid",
    "url": "/api/v1/files/uuid",
    "name": "document.pdf",
    "collection_name": "file-96xxxxxx...",
    "status": "uploaded",
    "size": 10486578,
    "error": "",
    "itemId": "uuid"
}]
```

### Accessing Physical File

```python
from pathlib import Path
the_file = Path(f"/app/backend/data/uploads/{__files__[0]['file']['id']}_{__files__[0]['file']['filename']}")
assert the_file.exists()
```

## `__tools__` Structure

Each element in `__tools__` is a `ToolUserModel` containing:

```python
{
    "id": "uuid",
    "user_id": "uuid",
    "name": "Tool Display Name",
    "content": "# Python source code...",
    "specs": [{...}],  # JSON schema of tool functions
    "meta": {"description": "...", "manifest": {...}},
    "valves": {...},
    "access_control": {...},
    "user": {"id": "uuid", "name": "...", "email": "...", "role": "..."},
    "callable": <function or functools.partial>,
    "# ... other tool model fields"
}
```

> **Security warning:** For async tools, the `callable` field is a `functools.partial` that may expose sensitive data (`__user__`, `__event_emitter__`). See [13-security.md](13-security.md) § functools.partial leak.

## `__oauth_token__` Structure

```python
{
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "refresh_token": "...",  # If supported by provider
    "expires_at": 1740000000  # Unix timestamp, auto-refreshed
}
```

> Recommended method for authenticated API calls: use `__oauth_token__["access_token"]` in Authorization headers rather than storing API keys in Valves.

## Behavior When a Reserved Parameter is Unavailable

When a reserved parameter is requested in the signature but is not available in the current context (e.g., `__event_call__` without live WebSocket connection, `__oauth_token__` without OAuth configured), the injected value is **`None`. No error is raised** — it is the developer's responsibility to check availability:

```python
async def my_tool(self, query: str, __event_call__=None) -> str:
    if __event_call__ is None:
        return "Degraded mode: bidirectional interaction unavailable"
    result = await __event_call__({...})
```
