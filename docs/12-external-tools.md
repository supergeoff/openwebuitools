# External Tools (OpenAPI + MCP)

Open WebUI supports two types of external tools: **OpenAPI** servers and **MCP (Model Context Protocol)** servers. These tools run outside the Open WebUI process and are accessible to the LLM via function calling.

> For most deployments, **OpenAPI** remains the preferred integration path.
>
> Source: https://docs.openwebui.com/features/extensibility/mcp.mdx + https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/index.mdx — consulted 04/13/2026

## OpenAPI Tool Servers

### Why OpenAPI

- Established standard, production-proven
- No proprietary protocol — if you're building REST APIs, you're already ready
- Easy integration and flexible hosting
- Solid security: HTTPS, OAuth, JWT, API Keys
- Rich tool ecosystem (code generation, documentation, validation, mocking)
- Future-proof and stable

### Limitations

- **One-way events only:** OpenAPI tools can emit status updates and notifications via the REST endpoint, but interactive events (confirmation, user input) are reserved for native Python tools
- **No streaming:** Responses are returned in bulk, not token by token
- CORS required for local servers

> Source: https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/index.mdx — consulted 04/13/2026

### Quickstart

```bash
git clone https://github.com/open-webui/openapi-servers
cd openapi-servers/servers/time
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --reload
```

The server is accessible at `http://localhost:8000`. Interactive documentation at `http://localhost:8000/docs`.

### Connection in Open WebUI

1. Open **⚙️ Settings → ➕ Tools**
2. Enter the server URL (e.g., `http://localhost:8000`)
3. Click "Save"

### CORS — Essential for Local Servers

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**HTTPS in production:** If Open WebUI is served over HTTPS, local servers must also be HTTPS, or run on localhost (127.0.0.1).

### operationId

It is important to define a custom `operationId` for all endpoints.

### Configuration via Environment Variable

`TOOL_SERVER_CONNECTIONS`: JSON array of connection configurations. Supports types `"openapi"` and `"mcp"`.

```json
[
  {
    "type": "openapi",
    "url": "http://example.com/api",
    "spec_type": "url",
    "spec": "",
    "path": "openapi.json",
    "auth_type": "bearer",
    "key": "your_api_key",
    "config": {"enable": true},
    "info": {
      "id": "server-1",
      "name": "Example OpenAPI Tool Server",
      "description": "Connects to an example OpenAPI tool."
    }
  },
  {
    "type": "mcp",
    "url": "http://localhost:3000/sse",
    "auth_type": "oauth_2.1",
    "key": "",
    "config": {"enable": true},
    "info": {
      "id": "server-2",
      "name": "Example MCP Server",
      "description": "Connects to an example MCP server."
    }
  }
]
```

> **MCP Stability:** MCP support is under continuous improvement. The wider ecosystem is still evolving — expect occasional breaking changes.

> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui.mdx — consulted 04/13/2026

### Any Framework/Language

FastAPI, Flask+Flask-RESTX, Express+Swagger, Spring Boot, Go with Swag... The only requirement is a valid OpenAPI spec with operationIds.

### Possible Tool Types

- Filesystem operations (read/write, list directories)
- Git and repository access
- Database queries
- Web scrapers / summarizers
- SaaS integrations (Salesforce, Jira, Slack)
- Memory / RAG components
- Secured internal microservices

---

## MCP (Model Context Protocol)

Natively available since **v0.6.31**. Supports **Streamable HTTP transport only** (not stdio, not native SSE).

> Open WebUI is a multi-tenant web environment, not a local desktop process. Long-running stdio/SSE connections are incompatible with this architecture.

### Prerequisite: WEBUI_SECRET_KEY

You **MUST** set `WEBUI_SECRET_KEY` in your Docker config. Without it, MCP OAuth tools will break on every restart (Error: `Error decrypting tokens`).

### Configuration

1. Open **⚙️ Admin Settings → External Tools**
2. Click **+ (Add Server)**
3. Set **Type** to **MCP (Streamable HTTP)**
4. Enter **Server URL** and **Auth** details
5. **Save**

### Common Error: Wrong Connection Type

If you add an MCP server by selecting the **OpenAPI** type, the UI will crash or display an infinite loading screen.

**Solution:**
1. Disable the problematic connection via Admin Settings
2. Refresh (Ctrl+F5)
3. Re-add with the correct Type **MCP (Streamable HTTP)**

### Authentication Modes

| Mode | When to Use |
|------|-------------|
| **None** | Local servers or internal network without token. **Use by default** unless the server explicitly requires a token. |
| **Bearer** | Only if the server requires a specific API token. **Key field is mandatory.** |
| **OAuth 2.1** | Dynamic Client Registration (DCR). When the server supports automatic OAuth client registration. |
| **OAuth 2.1 (Static)** | When you already have a pre-created client ID/secret from your IdP. |

**Bearer warning:** Selecting "Bearer" without providing a key sends an empty `Authorization: Bearer` header, which causes immediate rejection by many servers.

### OAuth 2.1 (Static) Setup

1. Select **OAuth 2.1 (Static)** in Auth
2. Enter **Client ID** and **Client Secret**
3. Click **Register Client**
4. **Save**
5. Open a chat → **+ → Integrations → Tools** → enable the MCP tool
6. Complete the OAuth flow in the browser

### OAuth 2.1 Limitation: No Default Tools

**Do not set OAuth 2.1 MCP tools as default/pre-enabled on a model.** The OAuth flow requires interactive browser redirection that cannot occur during a chat completion request.

**Workaround:** Users manually enable OAuth 2.1 tools per chat via the **➕** button in the input area.

### Connection URLs in Docker

If Open WebUI runs in Docker and the MCP server is on the host machine:
- Use `http://host.docker.internal:<port>` (e.g., `http://host.docker.internal:3000/sse`) instead of `localhost`

### Function Name Filter List

Restricts which tools are exposed to the LLM. Leave empty to expose all tools.

**Bug workaround:** If connection error with an empty list, add a simple comma (`,`) to force the system to treat the field as a valid filter.

---

## MCPO — MCP Proxy to OpenAPI

For MCP servers using **stdio** or **SSE** (non-Streamable HTTP), the [mcpo](https://github.com/open-webui/mcpo) proxy translates transports into compatible OpenAPI endpoints.

### Quickstart

```bash
uvx mcpo --port 8000 -- uvx mcp-server-time --local-timezone=America/New_York
```

The server is accessible at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.

### Dockerfile for Production

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install mcpo uv
CMD ["uvx", "mcpo", "--host", "0.0.0.0", "--port", "8000", "--", "uvx", "mcp-server-time", "--local-timezone=America/New_York"]
```

> The `--host 0.0.0.0` flag is required in Docker containers to expose the service on all network interfaces.

### How It Works

- At startup, the proxy connects to the MCP server to discover tools
- It automatically constructs FastAPI endpoints based on MCP schemas
- Auto-generated Swagger UI documentation
- Asynchronous and performant

### Supported Events

Tools exposed via mcpo can emit events (status, notifications) via Open WebUI's REST endpoint. Headers `X-Open-WebUI-Chat-Id` and `X-Open-WebUI-Message-Id` are automatically passed.

> Source: https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/mcp.mdx — consulted 04/13/2026

---

## MCP vs OpenAPI: When to Choose What

| Criterion | OpenAPI | MCP |
|-----------|---------|-----|
| Production-ready | ✅ Mature standard | ⚠️ Evolving |
| SSO / API gateways | ✅ Native | ❌ Limited |
| Observability | ✅ Tracing, audit | ⚠️ Basic |
| Streaming protocol | ❌ Full response | ✅ Streamable HTTP |
| Tool ecosystem | ✅ Massive | 🔄 Growing |
| Setup complexity | Low (standard REST) | Medium (new protocol) |
| Multi-tenant web | ✅ Designed for | ⚠️ CORS/CSRF limits |

> You don't have to choose: many teams expose OpenAPI internally and wrap MCP at the edge for specific clients.
