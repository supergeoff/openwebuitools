# Creating a Pipe (custom model/agent)

A Pipe Function appears as a **standalone model** in the Open WebUI interface. The user selects it like any other model, and the Pipe processes the request with its custom logic.

## Basic Structure

```python
from pydantic import BaseModel, Field

class Pipe:
    class Valves(BaseModel):
        API_KEY: str = Field(default="", description="Authentication credential")
        NAME_PREFIX: str = Field(default="PREFIX/", description="Display prefix")
        BASE_URL: str = Field(default="https://api.example.com", description="Endpoint")
    
    def __init__(self):
        self.valves = self.Valves()
    
    def pipes(self) -> list:
        return [
            {"id": "model-1", "name": "Display Name 1"},
            {"id": "model-2", "name": "Display Name 2"}
        ]
    
    async def pipe(self, body: dict, __user__: dict, __request__: Request) -> Any:
        model_id = body.get("model", "")
        pass
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ — consulted 04/13/2026

## The `pipe()` Method

This is the main method called when the user sends a message to the Pipe model.

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|-------------|-------------|
| `body` | dict | Yes | Request payload (model, stream, messages, etc.) |
| `__user__` | dict | No | User information |
| `__request__` | Request | **Yes since 0.5.0** | FastAPI Request object |
| `__event_emitter__` | Callable | No | One-way communication to frontend |
| `__event_call__` | Callable | No | Bidirectional communication with user |
| `__metadata__` | dict | No | Enriched context metadata |
| `__messages__` | list | No | List of messages (identical to `body["messages"]`) |
| `__files__` | list | No | List of file objects |
| `__model__` | dict | No | Complete model object |
| `__tools__` | list | No | List of ToolUserModel instances (to call other tools) |
| `__chat_id__` | str | No | Conversation UUID |
| `__session_id__` | str | No | Session identifier |
| `__message_id__` | str | No | Current message identifier |

> **Breaking change v0.5.0:** `__request__` has become mandatory. Without it, calls to `generate_chat_completion` and other internal functions will not work.

### Return

The `pipe()` method can return:
- `str` — simple text response
- `Generator` / `Iterator` — for streaming
- `AsyncGenerator` — for async streaming
- Dict in OpenAI chat completion format

### Streaming

```python
if body.get("stream", False):
    return r.iter_lines()  # Iterator for streaming
else:
    return r.json()  # Full response
```

## The `pipes()` Method — Manifold Pattern

The `pipes()` method returns a list of models. Each entry appears as a selectable model in the interface. The selected model is routed via `body["model"]`.

```python
def pipes(self) -> list:
    return [
        {"id": "model-1", "name": "Display Name 1"},
        {"id": "model-2", "name": "Display Name 2"}
    ]
```

The selected model ID is available in `body["model"]` as `pipe_id.sub_id` (e.g., `my_pipe.model-1`).

### Pipe without `pipes()`

If the `pipes()` method is not defined, the Pipe appears in the UI as a **single model** with the Pipe name (`self.name`). This is the simplest case for a Pipe that only handles one model.

### Using `__tools__` in a Pipe

A Pipe can access available tools via the `__tools__` parameter to call other tools:

```python
async def pipe(self, body: dict, __tools__=None, __user__=None, __request__=None) -> str:
    if __tools__:
        for tool in __tools__:
            if tool.get("name") == "search_tool":
                result = await tool["callable"]("search query")
                # Use the result...
    return "Response based on tool output"
```

> **Security warning:** For async tools, `tool["callable"]` is a `functools.partial` that may expose sensitive data. See [13-security.md](13-security.md).

### Manifold in External Pipelines

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

## Accessing Open WebUI Internal Functions

A Pipe can call Open WebUI internal functions:

```python
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

# v0.9.0+: async
user_obj = await Users.get_user_by_id(__user__["id"])
result = await generate_chat_completion(__request__, body, user_obj)
```

### Before v0.9.0 (sync)

```python
user_obj = Users.get_user_by_id(__user__["id"])
result = await generate_chat_completion(__request__, body, user_obj)
```

## Pipeline Scaffolds — Lifecycle Hooks

External Pipelines have additional hooks:

```python
class Pipeline:
    async def on_startup(self):
        print(f"on_startup:{__name__}")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        pass
```

> Source: https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/example_pipeline_scaffold.py — consulted 04/13/2026
