# Migrations and Breaking Changes

## Migration 0.4 → 0.5.0

### Architectural Change

Sub-app architecture → single FastAPI app with multiple routers.

### Import Paths

| Before (0.4) | After (0.5) |
|-------------|-------------|
| `open_webui.apps.*` | `open_webui.routers.*` |
| `open_webui.apps.webui` | `open_webui.main` |
| `open_webui.apps.webui.models` | `open_webui.models` |

### New Mandatory Parameter

`__request__: Request` in all pipe functions. Without it, calls to `generate_chat_completion` and other internal functions will not work.

### API Replacement

```python
# BEFORE (0.4)
from open_webui.apps.ollama import generate_chat_completion

async def pipe(self, body: dict, __user__: dict) -> str:
    user = User(**__user__)
    return await generate_chat_completion(body, user)

# AFTER (0.5)
from open_webui.utils.chat import generate_chat_completion
from fastapi import Request

async def pipe(self, body: dict, __user__: dict, __request__: Request) -> str:
    user = User(**__user__)
    return await generate_chat_completion(__request__, body, user)
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 — consulted 04/13/2026

## Migration → 0.9.0

### Core Change

Data layer moves from synchronous to **end-to-end asynchronous**.

### Impact

All model methods (Users, Chats, Files, Models, Functions, Tools, Knowledges) return coroutines.

"Once one function in the chain becomes a coroutine, every caller does too, all the way up to your plugin's entrypoint"

### Database Sessions

`get_db_context` sync removed → `get_async_db_context` with `AsyncSession` and SQLAlchemy 2.0 async.

### Before/After Code

```python
# BEFORE (0.8.x)
def resolve_user(user_id: str):
    user = Users.get_user_by_id(user_id)
    chats = Chats.get_chat_list_by_user_id(user_id)
    return user, chats

# AFTER (0.9.0)
async def resolve_user(user_id: str):
    user = await Users.get_user_by_id(user_id)
    chats = await Chats.get_chat_list_by_user_id(user_id)
    return user, chats
```

### SQLAlchemy Query Patterns Changed

| Before | After |
|--------|-------|
| `.first()` | `.scalars().first()` |
| `.all()` | `.scalars().all()` |
| `.count()` | `.scalar_one()` |

### Using `get_async_db_context`

```python
from open_webui.internal.db import get_async_db_context
from sqlalchemy import select

async def query_with_db():
    async with get_async_db_context() as session:
        result = await session.execute(select(User).where(User.id == "uuid"))
        user = result.scalars().first()
```

### For Synchronous Dependencies

```python
import anyio
result = await anyio.to_thread.run_sync(legacy_client.fetch, url)
```

### Sync Methods That Became Async

Several CRUD methods changed from sync to async in v0.9.0:

| Before (0.8.x) | After (0.9.0+) |
|---------------|----------------|
| `Users.get_user_by_id(user_id)` | `await Users.get_user_by_id(user_id)` |
| `Chats.get_chat_list_by_user_id(user_id)` | `await Chats.get_chat_list_by_user_id(user_id)` |
| `Functions.get_function_by_id(func_id)` | `await Functions.get_function_by_id(func_id)` |
| `Tools.get_tool_by_id(tool_id)` | `await Tools.get_tool_by_id(tool_id)` |

> Source: https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 — consulted 04/13/2026
