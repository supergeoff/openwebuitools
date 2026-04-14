# Security, Limits and Best Practices

## Arbitrary Code Execution

"Workspace Tools and Functions execute arbitrary Python code on your server."

**Shell equivalence:** "Granting a user the ability to create or import Tools is equivalent to giving them shell access."

**Restriction:** Function/tool creation is restricted to administrators.

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consulted 04/13/2026

## Data Directory

In Docker: `/app/backend/data`

> Source: https://docs.openwebui.com/features/extensibility/plugin/ — consulted 04/13/2026

## Non-sandboxed JavaScript Risks

Execute events (via `__event_call__` or `__event_emitter__`) execute JavaScript in the **main page context**, without iframe sandbox:

"JavaScript runs in main page context with full DOM, cookie, and localStorage access—no iframe sandboxing"

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/events — consulted 04/13/2026

**Recommendation:** Never execute untrusted JavaScript code via execute events. Prefer Rich UI Embed (sandboxed iframe) for HTML content.

## allowSameOrigin Risks for Rich UI Embeds

Enabling `allowSameOrigin` (Settings → Interface → Allow Iframe Same-Origin Access) allows the iframe to access parent's cookies, localStorage, and DOM. **This is an XSS vector if the embedded HTML content is not trusted.**

**Recommendation:** Never enable `allowSameOrigin` with content from untrusted sources.

## Docker `--add-host` Flag Risks

The `--add-host=host.docker.internal:host-gateway` flag used in Pipeline and Open WebUI Docker commands allows the container to access host machine services. This is a potential risk in production if the container is compromised.

**Recommendation:** In production, limit container network access and use dedicated Docker networks rather than direct host access.

## Pipelines Risks

"A malicious Pipeline could access your file system, exfiltrate data, mine cryptocurrency, or compromise your system."

Pipelines run in their own container but have full access to that container's filesystem and network.

> Source: https://docs.openwebui.com/features/extensibility/pipelines/ — consulted 04/13/2026

## Data Leakage via `functools.partial` (Issue #16307)

**Problem:** When tool methods are async and accept `__user__`/`__event_emitter__`, the `__tools__` dict passed to pipes contains a `functools.partial` that exposes the complete user object and sensitive data.

**Exposed data:** API keys (`sk-...`), base64 profile images, email tool passwords, complete valve configurations, system parameters.

**Non-async behavior (expected):**
```python
'callable': <function Tools.get_temperature at 0x7f2fbb1ac860>
```

**Async behavior (problematic):**
```python
'callable': functools.partial(
    <bound method Tools.get_temperature>,
    __event_emitter__=<function>,
    __user__={...full user dict...}
)
```

**Status:** Closed as "intended behaviour", but security implications need reconsideration.

**Recommendation:** Pipe implementations must **manually filter sensitive data** before sending tool information to external LLM providers. The framework passes complete internal state via partial closures.

> Source: Issue #16307 — consulted 04/13/2026

## `__event_emitter__` Typing

Typing must be `Callable` or omitted (for automatic injection), **never `None`**:

```python
# INCORRECT — breaks injection
async def my_method(self, __event_emitter__: None):

# CORRECT
async def my_method(self, __event_emitter__=None):
```

> Source: Issue #8168 — consulted 04/13/2026

## pip install Runtime — Production Risks

`ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=True` (default) allows arbitrary package installation by third-party tools.

**Risks:**
- Installation of malicious packages
- Race conditions with `UVICORN_WORKERS > 1` or multiple replicas (pip locking)
- UI unresponsive during installation

**Production recommendation:**

```bash
ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False
```

Pre-install via Dockerfile:

```dockerfile
FROM ghcr.io/open-webui/open-webui:main
RUN pip install --no-cache-dir python-docx requests beautifulsoup4
```

> Source: Context7 (/open-webui/docs) — consulted 04/13/2026

## Security Recommendations

1. **Restrict Tools/Functions creation to administrators** — default configuration, maintain it
2. **Never install tools from untrusted sources** — always review code before import
3. **Disable pip install runtime in production**
4. **Manually filter sensitive data** in Pipes before sending to external LLMs
5. **Prefer Rich UI Embed (sandboxed iframe)** over execute events for HTML content
6. **Validate and sanitize all inputs** provided by the LLM
7. **Restrict permissions** for file/command operations
8. **Do not directly mount config.json** via Docker volume (causes `OSError: [Errno 16]` via `os.rename`) — use an entrypoint script instead
9. **In production, serve OpenAPI tool servers over HTTPS** — browsers block HTTP requests from HTTPS pages
