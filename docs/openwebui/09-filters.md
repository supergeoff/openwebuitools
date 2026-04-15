# Creating a Filter (pre/post-processing)

A Filter Function acts as middleware in the processing flow. It can modify input data (`inlet`), intercept streaming (`stream`), and modify output data (`outlet`).

## Basic Structure

```python
from pydantic import BaseModel, Field
from typing import Optional

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Lower values execute first")
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Creates a switch in the UI
        self.icon = "https://example.com/icon.svg"
    
    async def inlet(self, body: dict, __event_emitter__=None, __user__=None, __metadata__=None, __model__=None) -> dict:
        return body
    
    def stream(self, event: dict) -> dict:
        return event
    
    def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
        pass
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ — consulted 04/13/2026

## Methods

### `inlet()` — Pre-processing

- **Always called** (WebUI AND API)
- Receives data modified by previous filters (Filters execute in cascade according to their `priority`)
- Can inject additional body parameters
- **Non-modifiable reserved keys:** `metadata`, `features`, `tool_ids`, `files`, `skill_ids`
- **MUST return body**

```python
async def inlet(self, body: dict, __event_emitter__=None, __user__=None, __metadata__=None, __model__=None) -> dict:
    # Example: filter unwanted words
    user_message = body["messages"][-1]["content"]
    body["messages"][-1]["content"] = user_message.replace("bad_word", "[filtered]")
    return body
```

### `stream()` — Real-time Interception

- **Always called** (WebUI AND API)
- Operates on individual chunks during streaming
- Can be async (`async def stream(self, event: dict) -> dict`)
- Event structure:

```python
{
    "id": "chatcmpl-...",
    "choices": [{"delta": {"content": "text fragment"}}]
}
```

```python
def stream(self, event: dict) -> dict:
    # Example: transform streaming text
    if "choices" in event and event["choices"]:
        content = event["choices"][0].get("delta", {}).get("content", "")
        event["choices"][0]["delta"]["content"] = content.upper()
    return event
```

### `outlet()` — Post-processing

- **NOT called** for direct API requests to `/api/chat/completions`
- Called after WebUI chat completion only
- Can be sync or async
- Returns `None` (based on side effects) or modified `body` (returning modified `body` may work but behavior was affected by bug #8168 — now fixed)
- To trigger via API: `POST /api/chat/completed`

```python
async def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
    # Log, audit, notification...
    pass
```

## API Behavior

| Method | WebUI | Direct API `/api/chat/completions` |
|--------|-------|-------------------------------------|
| `inlet()` | ✅ Always called | ✅ Always called |
| `stream()` | ✅ Always called | ✅ Always called |
| `outlet()` | ✅ Called | ❌ NOT called |

## Global / Model-specific System

| State | is_active | is_global | Effect |
|------|-----------|-----------|---------|
| Globally enabled | ✅ True | ✅ True | Applies to ALL models (grayed in UI) |
| Globally disabled | ❌ False | Any | Not applied |
| Model-specific | ✅ True | ❌ False | Only on selected models |
| Inactive | ❌ False | ❌ False | Not applied |

## Toggleable vs Always-On

### Toggleable (`self.toggle = True`)

- Visible switches in UI
- User enable/disable per session
- Ideal for optional filters (e.g., translation, prompt enhancement)

### Always-On (no `self.toggle`)

- Executes automatically
- No user control
- Ideal for security, compliance, logging

## `self.icon`

URL of the icon displayed in the interface for the Filter.

## Complete Example: Word Filter

```python
from pydantic import BaseModel, Field
from typing import Optional
import re

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Lower values execute first")
        blocked_words: str = Field(default="bad1,bad2,bad3", description="Comma-separated words to filter")
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
    
    async def inlet(self, body: dict, __user__=None) -> dict:
        words = [w.strip() for w in self.valves.blocked_words.split(",")]
        content = body["messages"][-1]["content"]
        for word in words:
            content = re.sub(rf'\b{re.escape(word)}\b', '[filtered]', content, flags=re.IGNORECASE)
        body["messages"][-1]["content"] = content
        return body
    
    def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
        pass
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ + Medium article — consulted 04/13/2026

## Lessons from Known Bugs

### `__event_emitter__` in outlet (Issue #8168 — FIXED)

The typing of the `__event_emitter__` parameter must be `Callable` or omitted (for automatic injection), **not `None`**. The revert behavior in outlet was a bug that was fixed.

```python
# INCORRECT
async def outlet(self, body: dict, __event_emitter__: None) -> dict:

# CORRECT
async def outlet(self, body: dict, __event_emitter__=None) -> dict:
```

> Source: Issue #8168 — consulted 04/13/2026

## Filters in Pipelines Context

In the context of external Pipelines, filters have specific properties:

```python
class Pipeline:
    def __init__(self):
        self.type = "filter"  # Required for Pipeline to be treated as a filter
        self.name = "Filter"
        self.valves = self.Valves(**{"pipelines": ["llama3:latest"]})
    
    class Valves(BaseModel):
        pipelines: List[str] = []  # Target specific pipelines
        priority: int = 0
```

The `pipelines` valve allows targeting only specific pipelines. If empty, the filter applies to all pipelines.
