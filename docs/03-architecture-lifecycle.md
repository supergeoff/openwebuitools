# Technical Architecture and Lifecycle

## Global Data Flow

```
User Input → Inlet Filters → RAG Query → LLM Call → Outlet Filters → UI Display
                 ↓                                          ↓
            Pre-processing                            Post-processing
```

> Source: https://deepwiki.com/open-webui/docs/4.2-functions-system — consulted 04/13/2026
>
> **Warning:** DeepWiki is an AI-generated source with limited reliability. The flow diagram above was verified against source code but may contain approximations.

## Lifecycle of a Custom Function

### Storage

`function` table in database:

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Unique identifier |
| `user_id` | String | Creator |
| `name` | Text | Display name |
| `type` | Text | `"pipe"`, `"filter"`, or `"action"` |
| `content` | Text | Source Python code |
| `meta` | JSONField | `{description, manifest}` |
| `valves` | JSONField | Admin configuration |
| `is_active` | Boolean | Enabled or not |
| `is_global` | Boolean | Applies to all models |
| `updated_at` | BigInteger | Epoch timestamp |
| `created_at` | BigInteger | Epoch timestamp |

> Source: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/functions.py — consulted 04/13/2026

### Associated Pydantic Models

- **FunctionModel**: Complete representation
- **FunctionWithValvesModel**: With optional valves
- **FunctionResponse**: For API, excludes content field
- **FunctionForm**: Input (id, name, content, meta required)

### Main CRUD Methods

| Method | Role |
|--------|------|
| `insert_new_function()` | Creation with auto timestamps |
| `sync_functions()` | Batch synchronization (update existing, insert new, delete obsolete) |
| `get_function_by_id()` | Read |
| `get_functions_by_type()` | Filter by type |
| `get_global_filter_functions()` | Active global filters |
| `get_global_action_functions()` | Active global actions |
| `get_function_valves_by_id()` | Get valves |
| `get_user_valves_by_id_and_user_id()` | User valves (stored in user settings) |
| `update_function_valves_by_id()` | Update valves |
| `_get_access_grants()` | Read function access rights |
| `get_tools_by_user_id()` | Tools accessible by a given user |

### Loading and Execution

| Step | Function | Description |
|------|----------|-------------|
| Module loading | `get_function_module_by_id(request, pipe_id)` | Retrieves module with cache, initializes Valves from DB |
| Pipe model enumeration | `get_function_models(request)` | Enumerates all active pipe functions, handles manifolds (multiple pipes), generates composite IDs `pipe.id.sub_id` |
| Main execution | `generate_function_chat_completion(request, form_data, user, models)` | Extracts metadata, builds `extra_params` with injected parameters, loads module, executes pipe |
| Parameter injection | `get_function_params(function_module, form_data, user, extra_params)` | Uses `inspect.signature()` to match extra_params with parameters declared by the function |
| Pipe execution | `execute_pipe(pipe, params)` | Detects if function is async or sync, executes with injected parameters |
| Streaming response | If `form_data['stream']` is True | Responses wrapped in `StreamingResponse` in event-stream format. Supports: string, sync Generator, AsyncGenerator |

> Source: https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py — consulted 04/13/2026

## Tool Lifecycle

### Storage

`tool` table in database:

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | Unique identifier |
| `user_id` | String | Creator |
| `name` | Text | Display name |
| `content` | Text | Source Python code |
| `specs` | JSONField | JSON schema of tool functions |
| `meta` | JSONField | `{description, manifest}` |
| `valves` | JSONField | Admin configuration |
| `updated_at` | BigInteger | Epoch timestamp |
| `created_at` | BigInteger | Epoch timestamp |

> Source: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/tools.py — consulted 04/13/2026

### Associated Pydantic Models

- **ToolModel**: With access_grants
- **ToolUserModel**: With UserResponse
- **ToolAccessResponse**: With write_access boolean
- **ToolForm**: Input (id, name, content, meta, optional access_grants)

### Loading

`get_tools()` in `utils/tools.py` — checks access control, loads modules, applies Valves, injects parameters, handles name collisions.

### Tool Types

| Type | Description |
|------|-------------|
| Builtin | Hardcoded: search, code, memory |
| Local | DB + plugin loader |
| OpenAPI | External servers |
| Terminal | CLI |

> Source: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py — consulted 04/13/2026

### Invisible Parameter Injection

`get_async_tool_function_and_apply_extra_params()` — wraps functions to inject `__id__`, `__user__`, etc. while hiding them from the visible signature by the model.

> Source: https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py — consulted 04/13/2026

### Tool Access Control

3 levels:

| Level | Description |
|-------|-------------|
| Bypass admin | Administrators bypass restrictions |
| Owner (creator-only) | Only the creator can use the tool |
| Group-based grants | Access by user groups |

> "Attached workspace tool to a model does not bypass access control. When a user chats, Open WebUI checks whether that specific user has read access to each attached tool."
>
> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/ — consulted 04/13/2026

## Pipeline Scaffolds (External Pipelines)

Pipelines have specific lifecycle hooks:

| Hook | Description |
|------|-------------|
| `on_startup()` | Called when server starts |
| `on_shutdown()` | Called when server stops |
| `on_valves_updated()` | Called when valves are updated |

### Basic Pipeline Scaffold Example

```python
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from schemas import OpenAIChatMessage  # Only available in Pipelines context, not in Open WebUI main

class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.name = "Pipeline Example"
        pass

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    async def on_valves_updated(self):
        pass

    async def inlet(self, body: dict, user: dict) -> dict:
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        if body.get("title", False):
            print("Title Generation Request")
        return f"{__name__} response to: {user_message}"
```

> Source: https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/example_pipeline_scaffold.py — consulted 04/13/2026

### Filter Pipeline Scaffold Example

```python
"""
title: Filter Pipeline
author: Open WebUI
date: 2024-01-01
version: 1.0.0
license: MIT
description: A filter pipeline example
requirements: detoxify
"""

from typing import List, Optional
from pydantic import BaseModel

class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = []
        priority: int = 0

    def __init__(self):
        self.type = "filter"
        self.name = "Filter"
        self.valves = self.Valves(**{"pipelines": ["llama3:latest"]})

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        if body.get("title", False):
            print("Title Generation Request")
        return body
```

> Source: https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/filter_pipeline_scaffold.py — consulted 04/13/2026

### Manifold Pipeline Scaffold Example

```python
class Pipeline:
    def __init__(self):
        self.type = "manifold"
        self.name = "Manifold: "
        self.pipelines = [
            {"id": "pipeline-1", "name": "Pipeline 1"},
            {"id": "pipeline-2", "name": "Pipeline 2"},
        ]

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        return f"{model_id} response to: {user_message}"
```

> Source: https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/manifold_pipeline_scaffold.py — consulted 04/13/2026

### Function Calling Pipeline Scaffold Example

```python
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel

class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"
        self.name = "Function Calling: "
        self.pipes = [
            {"id": "function-calling", "name": "Function Calling"},
        ]

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # The function calling scaffold demonstrates how to expose
        # a pipeline with native function calling support
        return f"{model_id} response to: {user_message}"
```

> Source: https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/function_calling_scaffold.py — consulted 04/13/2026
