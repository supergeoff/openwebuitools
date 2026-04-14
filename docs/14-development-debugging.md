# Development, Testing and Debugging

## Deployment Methods

### 1. Direct Code Editor

Copy Python code directly into the Open WebUI workspace (Admin Panel → Workspace → Tools/Functions).

### 2. Community Marketplace

Import from `openwebui.com/t/<username>` (Tools) or `openwebui.com/f/<username>` (Functions).

> Source: Medium article "Optimize Open WebUI" — consulted 04/13/2026

### 3. JSON Files

Convert the `.py` file to `.json` format for upload.

### 4. Pre-loading Before First Startup (advanced)

Docker entrypoint script that:
1. Waits for Open WebUI to start
2. Creates admin via API signup
3. Registers functions via `POST /api/v1/functions/create`

> **Note:** The `/api/v1/functions/create` endpoint is not listed in the official API documentation.

**Deployment structure:**
```
├── webui/
│   ├── configs/
│   │   └── config_[locale].json
│   └── pipeline/
│       ├── mypipe_pipe.py
│       └── template.json
├── .service.webui.env
└── docker-compose.yml
```

> Source: GitHub Discussion #8955 — consulted 04/13/2026

### config.json Mount Problem

Mounting `config.json` directly via Docker volume causes `OSError: [Errno 16] Device or resource busy` — the application does an `os.rename` incompatible with mounts. **Workaround:** use the copy mechanism in the entrypoint rather than direct file mounting.

## Docker Configuration for Persistence

```bash
docker run -d -p 3000:8080 --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --mount type=bind,source="<local_path>",target=/app/data \
  --name open-webui ghcr.io/open-webui/open-webui:cuda
```

The bind mount "enables data exchange between isolated container and host system" — necessary for extensions to persist files locally.

> Source: Medium article "Optimize Open WebUI" — consulted 04/13/2026

## Common Errors and Solutions

| Problem | Cause | Solution |
|----------|-------|----------|
| "Something went wrong :/ list index out of range" | Missing docstrings or type hints | Add complete Sphinx-style docstrings and type hints |
| Tool never called by model | Tool not enabled for the model | Enable in workspace model settings |
| Tool missing from UI | Docker volume corruption | Reset Docker volume (not just the container) |
| Tool called but returns nothing | Model too weak | Use a more powerful model (gpt-4o, Llama 3.1) |
| ImportError for packages | Dependencies not installed | Add to frontmatter `requirements:` |
| `KeyError: 'type'` | Complex types in signatures | Use only `str`, `int`, `float`, `bool` |
| Action deletes message | `return body` instead of `return None` | Always return `None` from an Action |
| Corrupted characters in status descriptions | i18n bug after v0.5.0 | Avoid special characters or check rendering |
| __event_emitter__ not working | Typed `None` instead of `Callable` | Use `__event_emitter__=None` or omit the type |

> Source: GitHub Discussion #3134 + Various Issues — consulted 04/13/2026

## Debugging

### Docker Logs

```bash
docker logs open-webui
```

### Recommended Debugging Patterns

1. **Start simple:** test with direct prompts ("Tell the LLM to use it")
2. **Consult logs** for execution details
3. **Check docstrings:** cause #1 of silent errors
4. **Check type hints:** only `str`, `int`, `float`, `bool`
5. **Test Default mode first** before Native mode

### Additional pip Options

The `PIP_OPTIONS` environment variable controls pip install behavior for frontmatter packages:

```bash
PIP_OPTIONS="--upgrade --no-cache-dir"
```

## Community Best Practices

1. **Always include docstrings** — "Without a docstring the calling LLM doesn't know what the function is for."
2. **Mandatory type hints** on all parameters and returns (primitives only)
3. **Error handling:** wrap logic in try-except returning meaningful error strings
4. **Test locally** before production deployment
5. **Async support:** use `async`/`await` for network operations
6. **Result limitation** to avoid overwhelming the LLM
7. **`self.citation = True`** to display tool context

> Source: GitHub Discussion #3134 — consulted 04/13/2026

## Tool Skeleton Template

The [open-webui-tool-skeleton](https://github.com/pahautelman/open-webui-tool-skeleton) repository offers a starting template with an `EventEmitter` utility class:

```python
class EventEmitter:
    def __init__(self, event_emitter):
        self.event_emitter = event_emitter

    async def progress_update(self, description):
        await self.emit(description, "progress")

    async def error_update(self, description):
        await self.emit(description, "error")

    async def success_update(self, description):
        await self.emit(description, "success")

    async def emit(self, description, status_type):
        if not self.event_emitter:
            return
        await self.event_emitter({
            "type": "status",
            "data": {
                "description": description,
                "done": status_type != "progress",
            },
        })
```

**Template best practices:**

| Practice | Detail |
|----------|--------|
| Documentation | "Clear, detailed docstrings are the primary mechanism through which language models understand tool capabilities" |
| Design | Each method should handle a specific, focused task |
| Error handling | Gracefully handle API failures, invalid inputs, network problems via EventEmitter |
| Dependencies | Meticulously list all external packages in the requirements field |
| Security | Validate and sanitize all inputs provided by the LLM; restrict permissions |

> Source: https://github.com/pahautelman/open-webui-tool-skeleton — consulted 04/13/2026

## Recommended Models for Function Calling

| Model | Recommended Mode |
|-------|----------------|
| GPT-4o / GPT-5 | Default + Native |
| Claude 4.5 Sonnet | Default + Native |
| Gemini 3 Flash | Default + Native |
| MiniMax M2.5 | Native |
| Llama 3.1-GROQ | Default |
| mistral-small:22b-instruct | Default |

Standard Llama 3 8B models are **known to be unreliable** with native tool calling (Issue #9414). Default mode is more tolerant with less powerful models.
