# Creating an Action (interactive buttons)

An Action Function adds interactive buttons under assistant messages in the interface. On click, Python executes server-side with bidirectional communication via `__event_call__`.

## Basic Structure

```python
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        parameter_name: str = "default_value"
        priority: int = 0

    def __init__(self):
        self.valves = self.Valves()
    
    async def action(self, body: dict, __user__=None, __event_emitter__=None,
                     __event_call__=None, __model__=None, __request__=None, __id__=None,
                     __metadata__=None, __chat_id__=None, __message_id__=None):
        return {"content": "Modified message content"}
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/action/ — consulted 04/13/2026

**Critical requirement:** "Action functions should always be defined as `async`."

## Multi-Actions

A single Action class can expose multiple buttons via the `actions` list, defined as a **class attribute** (at the same level as `Valves`):

```python
class Action:
    actions = [
        {"id": "summarize", "name": "Summarize", "icon_url": "https://example.com/icons/summarize.svg"},
        {"id": "translate", "name": "Translate", "icon_url": "https://example.com/icons/translate.svg"}
    ]

async def action(self, body: dict, __id__=None, **kwargs):
    if __id__ == "summarize":
        return {"content": "Summary: ..."}
    elif __id__ == "translate":
        return {"content": "Translation: ..."}
```

The `__id__` parameter contains the ID of the clicked action.

## Button Order

"Action buttons beneath assistant messages are sorted by their `priority` valve value in **ascending order** — lower values appear first (leftmost)."

Without a `priority` valve, the order among equal priorities is determined **alphabetically by function ID**.

## Frontmatter

```python
"""
title: Enhanced Message Processor
author: @admin
version: 1.2.0
required_open_webui_version: 0.5.0
icon_url: https://example.com/icons/message-processor.svg
requirements: requests,beautifulsoup4
"""
```

**Supported fields:** title, author, version, required_open_webui_version, icon_url

**WARNING:** `icon_url` MUST use hosted URLs, **never base64**.

## Return Value — 3 Distinct Behaviors

```python
# Case 1: Return None — do NOT modify the message (recommended default)
async def action(self, body: dict, **kwargs):
    # ... logic (notification, file save, etc.)
    return None

# Case 2: Return {"content": "..."} — REPLACE message content
async def action(self, body: dict, **kwargs):
    return {"content": "Modified message content",
            "files": [{"type": "image", "url": "chart.png", "name": "Chart"}]}

# Case 3: Return body — DELETE the message (BUG, never do this)
async def action(self, body: dict, **kwargs):
    return body  # ← INCORRECT — causes unintentional message deletion
```

> Source: Issue #8292 — consulted 04/13/2026

## Complete Example: File Save

```python
async def action(self, body: dict, __user__=None, 
                __event_emitter__=None, __event_call__=None) -> None:
    response = await __event_call__({
        "type": "input",
        "data": {"title": "Filename", "message": "Enter filename", "placeholder": "output.txt"}
    })
    
    last_message = body["messages"][-1]["content"]
    
    with open(f"/app/data/{response}", "w") as f:
        f.write(last_message)
    
    await __event_emitter__({
        "type": "notification",
        "data": {"type": "success", "content": f"Saved to {response}"}
    })
```

> Source: Medium article "Optimize Open WebUI" — consulted 04/13/2026

## Docker Configuration for File Persistence

Actions that write files require a bind mount:

```bash
docker run -d -p 3000:8080 --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --mount type=bind,source="<local_path>",target=/app/data \
  --name open-webui ghcr.io/open-webui/open-webui:cuda
```

The bind mount "enables data exchange between isolated container and host system."
