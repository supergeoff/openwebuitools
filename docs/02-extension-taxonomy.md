# Open WebUI Extensibility System Taxonomy

## Three Layers of Extensibility

Open WebUI offers three distinct layers to extend its capabilities:

| Layer | Mechanism | Execution | Use Cases |
|-------|-----------|-----------|-----------|
| **1. In-process Python** | Tools & Functions | Within Open WebUI process | Custom logic, UI interaction, filtering |
| **2. External HTTP** | OpenAPI & MCP servers | External services | SaaS integrations, third-party APIs, hosted tools |
| **3. Pipeline workers** | Pipelines | Separate Docker container (port 9099) | Heavy tasks, custom packages, isolation |

> Source: https://docs.openwebui.com/features/extensibility/pipelines/ — consulted 04/13/2026

## Main Extension Types

### Tools (tools called by the LLM)

Python scripts executed in the Open WebUI environment, called by the LLM via function calling. Official definition: *"Python scripts that run directly within the Open WebUI environment"*. Two tool calling modes: **Default** (Legacy, prompt injection) and **Native** (Agentic, native model capabilities).

Managed in the **Workspace** tabs. Full Python capabilities.

> "Workspace Tools execute arbitrary Python code on your server. Only install from trusted sources, review code before importing, and restrict Workspace access to trusted administrators only. Granting a user the ability to create or import Tools is equivalent to giving them shell access."
>
> Source: https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consulted 04/13/2026

### Functions (three subtypes)

Managed from the **Admin Panel**. Help "the WebUI itself do more things, like adding new AI models". Execution via `exec` in the Open WebUI process.

#### Pipe Function (custom model/agent)

Appears as a **standalone model** in the interface. Processes requests with custom logic. Can expose multiple models via the Manifold pattern (`pipes()` returning a list).

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ — consulted 04/13/2026

#### Filter Function (pre/post-processing)

Modifies input data (`inlet`), streaming (`stream`), and output data (`outlet`) of the LLM. Acts as middleware.

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ — consulted 04/13/2026

#### Action Function (interactive buttons)

Interactive buttons in the message bar, executes Python server-side. Bidirectional communication with the user via `__event_call__`.

> Source: https://docs.openwebui.com/features/extensibility/plugin/functions/action/ — consulted 04/13/2026

### Pipelines (separate service)

Separate service deployed via Docker (`ghcr.io/open-webui/pipelines:main`), port 9099. **Python 3.11 required.** Recommended when "dealing with computationally heavy tasks that you want to offload from your main Open WebUI instance for better performance and scalability." Compatible with any client supporting the OpenAI API.

> Source: https://docs.openwebui.com/features/extensibility/pipelines/ — consulted 04/13/2026

### External Tools (OpenAPI & MCP)

- **OpenAPI Tool Servers**: External REST services exposing an OpenAPI spec. Integration via Admin Settings → External Tools.
- **MCP (Model Context Protocol)**: Standard protocol supported natively since v0.6.31. Streamable HTTP connection only.

> See [12-external-tools.md](12-external-tools.md) for complete details.

## Comparative Table

| Aspect | Tools | Pipe | Filter | Action | Pipeline | OpenAPI | MCP |
|--------|-------|------|--------|--------|----------|---------|-----|
| **Who calls** | The LLM (function calling) | User (model selection) | Automatic (middleware) | User (button click) | User (model selection) | The LLM (function calling) | The LLM (function calling) |
| **Where it runs** | Open WebUI process | Open WebUI process | Open WebUI process | Open WebUI process | Separate Docker container | External service | External service |
| **UI** | Workspace | Admin Panel (model) | Admin Panel (filter) | Buttons under messages | Admin Panel (model) | External Tools | External Tools |
| **Import packages** | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | Any package | N/A (external service) | N/A (external service) |
| **Events** | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | Via REST endpoint | One-way (REST endpoint) | One-way (REST endpoint) |
| **Rich UI** | HTMLResponse | No | No | HTMLResponse | No | No | No |
| **Valves** | Yes | Yes | Yes | Yes | Yes | N/A | N/A |

## Internal Functions vs External Pipelines

| Aspect | Internal Functions | External Pipelines |
|--------|-------------------|-------------------|
| Execution | Within Open WebUI process | Dedicated Docker container (port 9099) |
| Import packages | Via frontmatter `requirements` (runtime pip install mechanism, not a real native Python import) | Any Python package |
| Isolation | None (same process) | Isolated in its own container |
| Configuration | Admin Panel | Admin Panel > Settings > Connections |
| Connection | N/A | URL: `http://localhost:9099`, API key: `0p3n-w3bu!` |
| Deployment | Integrated | `docker run -d -p 9099:9099 --add-host=host.docker.internal:host-gateway -v pipelines:/app/pipelines --name pipelines --restart always ghcr.io/open-webui/pipelines:main` |
| Auto-loading | N/A | All pipelines in `/pipelines` are loaded at startup. Configurable via `PIPELINES_DIR` |

> "If your goal is simply to add support for additional providers...you likely don't need Pipelines." Use internal Functions for basic cases.
>
> Source: https://docs.openwebui.com/features/extensibility/pipelines/ — consulted 04/13/2026

## Known Nomenclature Confusion

The community has identified significant confusion in the taxonomy (GitHub Discussion #16415):

- 5 distinct categories create confusion: **Capabilities**, **Tools**, **Tool Servers**, **Functions** (Filters/Actions/Pipes), **Pipelines**
- "Tools" and "Capabilities" do similar things with different terms
- Documentation structure does not match UI organization (e.g., docs place "Filters" and "Pipes" under "Pipelines", but UI places them under "Functions")
- "Functions" combines 3 operations with fundamentally different user workflows

**Proposed community solution:** Merge "capabilities", "tools", and "tool servers" under unified "tools" with subcategories. Disaggregate "Functions" into distinct named categories.

> Source: https://github.com/open-webui/open-webui/discussions/16415 — consulted 04/13/2026
