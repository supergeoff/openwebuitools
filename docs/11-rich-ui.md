# Rich UI Embedding

Rich UI Embedding allows displaying interactive HTML content in the chat interface via `HTMLResponse` with a `Content-Disposition: inline` header. Content is rendered in a sandboxed iframe.

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ — consulted 04/13/2026

## Availability

| Type | Rich UI Supported |
|------|-----------------|
| Tools | ✅ |
| Actions | ✅ |
| Pipes | ❌ |
| Filters | ❌ |

## Render Position

- **Tools:** inline at the tool call indicator
- **Actions:** above message text

## Tool Implementation

```python
from fastapi.responses import HTMLResponse

def create_visualization_tool(self, data: str) -> HTMLResponse:
    html_content = """<!DOCTYPE html><html>...</html>"""
    headers = {"Content-Disposition": "inline"}
    return HTMLResponse(content=html_content, headers=headers)
```

## Providing Context to LLM (tuple)

By default, without custom context, the LLM receives: "Tool name: Embedded UI result is active and visible to the user."

To provide custom context to the LLM:

```python
def create_chart(self, data: str) -> tuple:
    html_content = "<html>...</html>"
    headers = {"Content-Disposition": "inline"}
    result_context = {"status": "success", "chart_type": "scatter", "data_points": 42}
    return HTMLResponse(content=html_content, headers=headers), result_context
```

## Iframe Height Management

The iframe does not know its own height. Two approaches:

### Via postMessage (recommended when allowSameOrigin is OFF)

```javascript
function reportHeight() {
    const h = document.documentElement.scrollHeight;
    parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
new ResizeObserver(reportHeight).observe(document.body);
```

### Auto-resize (allowSameOrigin ON)

When `allowSameOrigin` is enabled, the iframe can communicate directly with the parent and auto-resize.

## Sandbox

### Always-active Flags

- `allow-scripts` — JavaScript execution
- `allow-popups` — window.open()
- `allow-downloads` — Downloads

### User-configurable Flags (Settings → Interface)

- **"Allow Iframe Same-Origin Access"** — allowSameOrigin
- **"Allow Iframe Form Submissions"** — allowForms

### allowSameOrigin OFF (default)

- Complete isolation
- Iframe cannot access parent's cookies/localStorage/DOM
- Requires `postMessage` to report height
- Safest configuration

### allowSameOrigin ON

- Iframe accesses parent context
- Auto-resize without additional script
- Chart.js and Alpine.js **auto-injected** if detected in HTML content
- Requires trust in embedded content

## Advanced Communication

### Argument Injection (`window.args`)

Tools automatically inject parameters into `window.args`. Actions do NOT receive `window.args`.

```javascript
window.addEventListener('load', () => {
    const args = window.args; // JSON parameters passed to the tool
});
```

### Prompt Submission

| Type | Behavior |
|------|-------------|
| `input:prompt` | Fills input without submitting |
| `input:prompt:submit` | Fills and submits |
| `action:submit` | Submits current input text |

```javascript
parent.postMessage({ type: 'input:prompt:submit', text: 'Show summary' }, '*');
```

When `allowSameOrigin` is OFF, `input:prompt:submit` displays a confirmation dialog.

## Rich UI vs Execute Event

| Aspect | Rich UI Embed | Execute Event |
|--------|---------------|---------------|
| Environment | Sandboxed iframe | Main page (non-sandboxed) |
| Persistence | Saved in history | Ephemeral, lost on reload |
| Page access | Isolated by default | Full DOM/cookies/storage access |
| Forms | Requires allowForms | Always functional |
| Best use | Persistent dashboards, charts | Transient interactions, downloads |

## Reload Behavior

When a historical chat is reloaded, the HTML content of the Rich UI embed is **re-rendered from content saved in DB** (in the message's embeds). The iframe is recreated with the same HTML. There is no specific caching — each reload rebuilds the iframe from persisted data.

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ — consulted 04/13/2026
