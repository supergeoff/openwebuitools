# Migrations et breaking changes

## Migration 0.4 → 0.5.0

### Changement architectural

Sub-app architecture → single FastAPI app with multiple routers.

### Import paths

| Avant (0.4) | Après (0.5) |
|-------------|-------------|
| `open_webui.apps.*` | `open_webui.routers.*` |
| `open_webui.apps.webui` | `open_webui.main` |
| `open_webui.apps.webui.models` | `open_webui.models` |

### Nouveau paramètre obligatoire

`__request__: Request` dans toutes les fonctions pipe. Sans lui, les appels à `generate_chat_completion` et autres fonctions internes ne fonctionneront pas.

### Remplacement API

```python
# AVANT (0.4)
from open_webui.apps.ollama import generate_chat_completion

async def pipe(self, body: dict, __user__: dict) -> str:
    user = User(**__user__)
    return await generate_chat_completion(body, user)

# APRÈS (0.5)
from open_webui.utils.chat import generate_chat_completion
from fastapi import Request

async def pipe(self, body: dict, __user__: dict, __request__: Request) -> str:
    user = User(**__user__)
    return await generate_chat_completion(__request__, body, user)
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 — consultée le 13/04/2026

## Migration → 0.9.0

### Changement core

Data layer passe de synchrone à **asynchrone de bout en bout**.

### Impact

Tous les model methods (Users, Chats, Files, Models, Functions, Tools, Knowledges) retournent des coroutines.

"once one function in the chain becomes a coroutine, every caller does too, all the way up to your plugin's entrypoint"

### Sessions BDD

`get_db_context` sync supprimé → `get_async_db_context` avec `AsyncSession` et SQLAlchemy 2.0 async.

### Code avant/après

```python
# AVANT (0.8.x)
def resolve_user(user_id: str):
    user = Users.get_user_by_id(user_id)
    chats = Chats.get_chat_list_by_user_id(user_id)
    return user, chats

# APRÈS (0.9.0)
async def resolve_user(user_id: str):
    user = await Users.get_user_by_id(user_id)
    chats = await Chats.get_chat_list_by_user_id(user_id)
    return user, chats
```

### Patterns de requête SQLAlchemy changés

| Avant | Après |
|-------|-------|
| `.first()` | `.scalars().first()` |
| `.all()` | `.scalars().all()` |
| `.count()` | `.scalar_one()` |

### Utilisation de `get_async_db_context`

```python
from open_webui.internal.db import get_async_db_context
from sqlalchemy import select

async def query_with_db():
    async with get_async_db_context() as session:
        result = await session.execute(select(User).where(User.id == "uuid"))
        user = result.scalars().first()
```

### Pour les dépendances sync

```python
import anyio
result = await anyio.to_thread.run_sync(legacy_client.fetch, url)
```

### Méthodes sync devenues async

Plusieurs méthodes CRUD sont passées de sync à async en v0.9.0 :

| Avant (0.8.x) | Après (0.9.0+) |
|---------------|----------------|
| `Users.get_user_by_id(user_id)` | `await Users.get_user_by_id(user_id)` |
| `Chats.get_chat_list_by_user_id(user_id)` | `await Chats.get_chat_list_by_user_id(user_id)` |
| `Functions.get_function_by_id(func_id)` | `await Functions.get_function_by_id(func_id)` |
| `Tools.get_tool_by_id(tool_id)` | `await Tools.get_tool_by_id(tool_id)` |

> Source : https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 — consultée le 13/04/2026
