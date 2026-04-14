# Event System

The event system enables communication between the backend (your Python code) and the frontend (the user interface). Two complementary mechanisms exist.

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/events — consulted 04/13/2026

## `__event_emitter__` — One-way Communication

Backend → Frontend. Sending events without waiting for a response.

```python
await __event_emitter__({"type": "event_type", "data": {...}})
```

**Availability:** Tools ✅, Actions ✅, Pipes ✅, Filters ✅

## `__event_call__` — Bidirectional Communication

Backend → Frontend → Backend. Waits for user response.

**Default timeout:** 300 seconds (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`)

**Availability:** Tools ✅, Actions ✅, Pipes ✅, Filters ✅

## Complete Event Types Reference

| Type | Helper | Data Structure | Persisted to DB |
|------|--------|----------------|------------------|
| `status` | `__event_emitter__` | `{description: str, done: bool, hidden: bool}` | Yes (statusHistory) |
| `chat:message:delta` / `message` | `__event_emitter__` | `{content: str}` | `message` yes (content), `chat:message:delta` no |
| `chat:message` / `replace` | `__event_emitter__` | `{content: str}` | `replace` yes (content, overwrites), `chat:message` no |
| `files` / `chat:message:files` | `__event_emitter__` | `{files: [...]}` | `files` yes |
| `chat:title` | `__event_emitter__` | `{title: str}` | No (Socket.IO only) |
| `chat:tags` | `__event_emitter__` | `{tags: [...]}` | No (Socket.IO only) |
| `source` / `citation` | `__event_emitter__` | Open WebUI Source/Citation Object (see Citations section below) | Yes (sources) |
| `embeds` / `chat:message:embeds` | `__event_emitter__` | `{embeds: [...]}` | `embeds` yes |
| `notification` | `__event_emitter__` | `{type: "info"|"success"|"warning"|"error", content: str}` | No (Socket.IO only) |
| `chat:message:error` | `__event_emitter__` | `{error: str}` | No (Socket.IO only) |
| `chat:message:follow_ups` | `__event_emitter__` | `{follow_ups: [...]}` | No (Socket.IO only) |
| `confirmation` | `__event_call__` | `{title: str, message: str}` | N/A (requires live connection) |
| `input` | `__event_call__` | `{title: str, message: str, placeholder: str, value: any, type: "password"|optional}` | N/A (requires live connection) |
| `execute` | Both | `{code: "...javascript..."}` | No |
| `chat:message:favorite` | `__event_emitter__` | `{favorite: bool}` | No (Socket.IO only) |
| `chat:completion` | `__event_emitter__` | Custom | No (Socket.IO only) |

## Event Persistence

| Category | Events | Behavior |
|----------|--------|----------|
| **Persisted to DB** | `status` → statusHistory, `message` → content, `replace` → content (overwrites), `embeds` → embeds, `files` → files, `source`/`citation` → sources | Survive disconnection |
| **Not persisted** | `chat:completion`, `chat:message:delta`, `chat:message:error`, `chat:message:follow_ups`, `chat:message:favorite`, `chat:title`, `chat:tags`, `notification` | Socket.IO only, lost on disconnection |
| **Require live connection** | `confirmation`, `input`, `execute` via `__event_call__` | Error if disconnected, 300s timeout |

> **Important:** Use short names (`message`, `replace`, `files`, `status`, `source`) for DB persistence. Long names (`chat:message:delta`, `chat:message:files`) work on the frontend side but do not persist.

## Compatibility Matrix by Function Type

| Capability | Tools | Actions | Pipes | Filters |
|------------|-------|---------|-------|---------|
| `__event_emitter__` | ✅ | ✅ | ✅ | ✅ |
| `__event_call__` | ✅ | ✅ | ✅ | ✅ |
| Return value → user response | ✅ | ✅ | ✅ | ❌ |
| `HTMLResponse` → Rich UI embed | ✅ | ✅ | ❌ | ❌ |

## Code Examples

### Status Event

```python
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Step 1/3: Fetching data...",
        "done": False,
        "hidden": False,
    },
})
# IMPORTANT: Always emit a final status with done: True to stop the shimmer animation
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Done!",
        "done": True,
    },
})
```

### Confirmation (bidirectional)

```python
result = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Are you sure?",
        "message": "Do you really want to proceed?"
    }
})
if result:
    pass  # User confirmed
else:
    pass  # User cancelled
```

### Input (bidirectional)

```python
result = await __event_call__({
    "type": "input",
    "data": {
        "title": "Enter your name",
        "message": "We need your name to proceed.",
        "placeholder": "Your full name"
    }
})
user_input = result
```

### Input password

```python
result = await __event_call__({
    "type": "input",
    "data": {
        "title": "Enter API Key",
        "message": "Your API key is required.",
        "placeholder": "sk-...",
        "type": "password"
    }
})
```

### Execute JavaScript (bidirectional with return)

```python
result = await __event_call__({
    "type": "execute",
    "data": {
        "code": "return document.title;",
    }
})
```

### Execute JavaScript (fire-and-forget)

```python
await __event_emitter__({
    "type": "execute",
    "data": {
        "code": """
            (function() {
                const blob = new Blob([data], {type: 'application/octet-stream'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'file.bin';
                document.body.appendChild(a);
                a.click();
                URL.revokeObjectURL(url);
                a.remove();
            })();
        """
    }
})
```

### Custom Form via execute

```python
result = await __event_call__({
    "type": "execute",
    "data": {
        "code": """
            return new Promise((resolve) => {
                const overlay = document.createElement('div');
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999';
                overlay.innerHTML = `
                    <div style="background:white;padding:24px;border-radius:12px;min-width:300px">
                        <h3 style="margin:0 0 12px">Enter Details</h3>
                        <input id="exec-name" placeholder="Name" style="width:100%;padding:8px;margin:4px 0;border:1px solid #ccc;border-radius:6px"/>
                        <input id="exec-email" placeholder="Email" style="width:100%;padding:8px;margin:4px 0;border:1px solid #ccc;border-radius:6px"/>
                        <button id="exec-submit" style="margin-top:12px;padding:8px 16px;background:#333;color:white;border:none;border-radius:6px;cursor:pointer">Submit</button>
                    </div>
                `;
                document.body.appendChild(overlay);
                document.getElementById('exec-submit').onclick = () => {
                    const name = document.getElementById('exec-name').value;
                    const email = document.getElementById('exec-email').value;
                    overlay.remove();
                    resolve({ name, email });
                };
            });
        """
    }
})
# result = {"name": "...", "email": "..."}
```

### Citation

```python
class Tools:
    def __init__(self):
        self.citation = False  # REQUIRED to use custom citations

    async def research_tool(self, topic: str, __event_emitter__=None) -> str:
        if not __event_emitter__:
            return "Research completed (citations not available)"

        sources = [
            {
                "title": "Advanced AI Systems",
                "url": "https://example.com/ai-systems",
                "content": "Artificial intelligence systems have evolved...",
                "author": "Dr. Jane Smith",
                "date": "2024-03-15"
            }
        ]

        for source in sources:
            await __event_emitter__({
                "type": "citation",
                "data": {
                    "document": [source["content"]],
                    "metadata": [{
                        "date_accessed": datetime.now().isoformat(),
                        "source": source["title"],
                        "author": source["author"],
                        "publication_date": source["date"],
                        "url": source["url"]
                    }],
                    "source": {
                        "name": source["title"],
                        "url": source["url"]
                    }
                }
            })

        return f"Research on '{topic}' completed. Found {len(sources)} sources."
```

> Citations work identically in Default and Native modes. For distinct citations, ensure that each citation's identifiers are different (the grouping mechanism merges citations with the same ID — Issue #17366).

### Customizable Citation Metadata

The `metadata` field of citations supports extended fields based on source type:

```python
# Academic citation
await __event_emitter__({
    "type": "citation",
    "data": {
        "document": [source["content"]],
        "metadata": [{
            "date_accessed": datetime.now().isoformat(),
            "source": source["title"],
            "authors": source["authors"],
            "journal": source["journal"],
            "volume": source["volume"],
            "pages": source["pages"],
            "doi": source["doi"],
            "publication_date": source["date"],
            "type": "academic_journal"
        }],
        "source": {"name": f"{source['title']} - {source['journal']}", "url": f"https://doi.org/{source['doi']}"}
    }
})

# Database record
await __event_emitter__({
    "type": "citation",
    "data": {
        "document": [record["data"]],
        "metadata": [{
            "date_accessed": datetime.now().isoformat(),
            "source": f"Database Table: {record['table']}",
            "record_id": record["record_id"],
            "last_updated": record["last_updated"],
            "type": "database_record"
        }],
        "source": {"name": f"Record {record['record_id']}", "url": f"db://{record['table']}/{record['record_id']}"}
    }
})
```

**Known `type` values:** `"academic_journal"`, `"database_record"`, `"web_page"`, etc.

## Events for External Tools

External tools (OpenAPI/MCP) can emit events via a REST endpoint.

**Prerequisite:** Environment variable `ENABLE_FORWARD_USER_INFO_HEADERS=True`

**Headers automatically provided:**
- `X-Open-WebUI-Chat-Id`
- `X-Open-WebUI-Message-Id` (configurable names)

**Endpoint:** `POST /api/v1/chats/{chat_id}/messages/{message_id}/event` with API key/session token auth

**Payload:**

```json
{
    "type": "status",
    "data": {
        "description": "Processing...",
        "done": false
    }
}
```

> The payload follows the same structure as `__event_emitter__`: an object with `type` and `data`.

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/events — consulted 04/13/2026

**Limitation:** Only one-way events (status, notification) are available for external tools. Interactive events (confirmation, input) require native Python tools.
