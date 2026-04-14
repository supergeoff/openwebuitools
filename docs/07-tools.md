# Creating a Tool (tool called by the LLM)

A Tool is a Python script executed in the Open WebUI environment, called by the LLM via function calling. The LLM decides when and how to call your Tool's methods based on their descriptions (docstrings) and signatures.

## Basic Structure

```python
"""
title: String Inverse
author: Your Name
author_url: https://website.com
git_url: https://github.com/username/string-reverse.git
description: This tool calculates the inverse of a string
required_open_webui_version: 0.4.0
requirements: langchain-openai, langgraph, ollama
version: 0.4.0
licence: MIT
"""

from pydantic import BaseModel, Field

class Tools:
    def __init__(self):
        self.valves = self.Valves()
    
    class Valves(BaseModel):
        api_key: str = Field("", description="Your API key here")
    
    class UserValves(BaseModel):
        preference: str = Field("default", description="User preference")
    
    async def reverse_string(self, string: str) -> str:
        """
        Reverses the input string.
        :param string: The string to reverse
        """
        return string[::-1]
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consulted 04/13/2026

## Critical Requirements

### Mandatory Type Hints

Every method argument **must** have a type hint. The system uses type hints to generate the JSON schema transmitted to the LLM.

**Only 4 primitive types are supported by the schema builder:** `str`, `int`, `float`, `bool`.

Any complex type (`Optional[str]`, `Dict[str, Any]`, `Union[int, str]`, `List[...]`) causes silent errors or `KeyError: 'type'`.

> Source: GitHub Discussion #13174 — consulted 04/13/2026

### Mandatory Docstrings

"Without a docstring the calling LLM doesn't know what the function is for." Docstrings must describe each parameter with the syntax `:param name: description`.

**Missing docstrings or type hints = "list index out of range" errors.**

> Source: GitHub Discussion #3134 — consulted 04/13/2026

### Recommended Async Methods

Async methods are recommended for future compatibility and network operations.

## Frontmatter (metadata in docstring)

The triple-quote block at the top of the file defines the Tool's metadata:

| Field | Description |
|-------|-------------|
| `title` | Display name in UI |
| `author` | Creator |
| `author_url` | Optional link to profile |
| `git_url` | Optional link to source repo |
| `description` | Brief description |
| `required_open_webui_version` | Minimum required version |
| `requirements` | Pip packages separated by commas |
| `version` | Tool version |
| `licence` | Distribution license |

## Managing External Packages

### Automatic Installation via Frontmatter

```python
"""
requirements: langchain-openai>=0.1.0,requests,beautifulsoup4
"""
```

The system automatically installs packages listed in `requirements:` via pip.

**WARNING:** "When multiple tools define different versions of the same package... Open WebUI installs them in a non-deterministic order."

### Production: Disable Runtime pip install

The `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` variable (default: `True`) controls automatic installation.

**In production, it is strongly recommended to disable it:**

```bash
ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False
```

Reasons:
- Prevents arbitrary package installation by third-party tools
- Eliminates race conditions when `UVICORN_WORKERS > 1` or multiple replicas
- Ensures reproducible deployments

**Alternative:** Pre-install packages via Dockerfile:

```dockerfile
FROM ghcr.io/open-webui/open-webui:main
RUN pip install --no-cache-dir python-docx requests beautifulsoup4
```

### Additional pip Options

The `PIP_OPTIONS` environment variable controls pip install behavior:

```bash
PIP_OPTIONS="--upgrade --no-cache-dir"
```

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/development/ + Context7 — consulted 04/13/2026

## Tool Calling Modes

### Default Mode (Legacy)

- Injection in the prompt
- Universal compatibility
- "Breaks KV cache" between turns
- Does not support system tools

### Native Mode (Agentic)

- Uses native function-calling capability of the model
- Structured definitions, multi-step
- Requires frontier models (GPT-5, Claude 4.5 Sonnet, Gemini 3 Flash, MiniMax M2.5)
- **CRITICAL INCOMPATIBILITY:** "Message events (message, chat:message, chat:message:delta, replace) are BROKEN in Native mode because the server emits repeated content snapshots that overwrite tool-emitted updates."

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/ — consulted 04/13/2026

### Event Compatibility by Mode

| Event Type | Default Mode | Native Mode | Status |
|------------|-------------|-------------|--------|
| status | ✅ Full | ✅ Identical | Compatible |
| message | ✅ Full | ❌ Broken | Incompatible |
| citation | ✅ Full | ✅ Identical | Compatible |
| notification | ✅ Full | ✅ Identical | Compatible |
| files | ✅ Full | ✅ Identical | Compatible |
| replace | ✅ Full | ❌ Broken | Incompatible |
| chat:message:delta | ✅ Full | ❌ Broken | Incompatible |

### Mode Detection Pattern

```python
async def adaptive_tool(self, __event_emitter__=None, __metadata__=None) -> str:
    mode = "default"
    if __metadata__:
        mode = __metadata__.get("function_calling", "default")
    is_native = (mode == "native")
```

> **Note:** `function_calling` is a top-level key in `__metadata__`, not under `params`. You can also find `__model__["info"]["params"]["function_calling"]` in the model structure.

## `self.citation = True`

Enables display of tool context in frontend responses. Set to `False` to use custom citations via `__event_emitter__`.

```python
class Tools:
    def __init__(self):
        self.citation = True  # Automatically displays context
```

> Source: GitHub Discussion #3134 — consulted 04/13/2026

## Built-in System Tools (Native Mode Only)

| Category | Tools | Description |
|----------|-------|-------------|
| Search & Web | `search_web`, `fetch_url` | Web queries, URL content extraction |
| Knowledge Base | `list_knowledge`, `query_knowledge_files`, `view_file`, etc. | KB navigation and extraction |
| Memory | `search_memories`, `add_memory`, `delete_memory` | Personalization management |
| Notes | `search_notes`, `write_note`, `view_note` | User notes operations |
| Chat History | `search_chats`, `view_chat` | Conversation history access |
| Code Interpreter | `execute_code` | Sandboxed code execution |
| Image Generation | `generate_image`, `edit_image` | Image creation and modification |
| Channels | `search_channels`, `view_channel_message` | Channel operations |
| Time Tools | `get_current_timestamp`, `calculate_timestamp` | Time calculations |

**Example signature:** `query_knowledge_files(query, knowledge_ids?, count=5)` → Returns `Array of {content, source, file_id, distance?}`

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/ — consulted 04/13/2026

## Community Examples

### Web Search (DuckDuckGo)

```python
from duckduckgo_search import DDGS

class Tools:
    def search_web(self, query: str) -> str:
        """Search web for query, return top 5 summaries."""
        try:
            results = DDGS().text(query, max_results=5)
            formatted = []
            for result in results:
                formatted.append(
                    f"Title: {result['title']}\n"
                    f"URL: {result['href']}\n"
                    f"Summary: {result['body']}"
                )
            return "\n---\n".join(formatted)
        except Exception as e:
            return f"Search error: {e}"
```

### Current Time

```python
from datetime import datetime

class Tools:
    def get_current_time(self) -> str:
        """Get current time in human-readable format."""
        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")
        current_date = now.strftime("%A, %B %d, %Y")
        return f"Current Date and Time = {current_date}, {current_time}"
```

### SQL Query (with Valves)

```python
import sqlite3
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        DB_PATH: str = Field(default="/path/db.sqlite3")
    
    def __init__(self):
        self.valves = self.Valves()
        self.citation = True
    
    def run_sql(self, query: str) -> str:
        """Execute read-only SQL query."""
        try:
            conn = sqlite3.connect(self.valves.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            return str(results)
        except Exception as e:
            return f"Error: {e}"
```

> Source: GitHub Discussion #3134 — consulted 04/13/2026

## Recommended Models for Function Calling

- GPT-4o / GPT-5 (OpenAI)
- Claude 4.5 Sonnet (Anthropic)
- Gemini 3 Flash (Google)
- Llama 3.1-GROQ
- mistral-small:22b-instruct

Weak models (standard Llama 3 8B) often fail to select the correct tool. The model must be trained on function-calling patterns to reliably invoke tools. Native tool calling mode heavily depends on model capability (Issue #9414).

> Source: GitHub Discussion #3134 + Issue #9414 — consulted 04/13/2026
