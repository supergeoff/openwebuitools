# Known Issues and Community Resources

## Resolved Bugs (for historical context)

| Bug | Version | Impact | Resolution | Issue |
|-----|---------|--------|------------|-------|
| `__event_emitter__` broken in outlet | v0.5.2 | No event emission from outlet filters | PR #8159 | #8168 |
| `__event_emitter__` broken in Actions | ~v0.5.x | `user_id` exception in Actions | PR #8246 | #8292 |
| Corrupted characters in status | v0.5.0+ | Unreadable status descriptions via i18n | Not documented | #8129 |
| Outlet content not persisted | v0.5.2 | Outlet modifications reverted after render | PR #8159 | #8168 |
| `__event_emitter__` error in pipe function | March 2025 | Errors when calling in pipes | Not resolved (?) | #11750 |

## Current Unresolved Limitations

| Limitation | Impact | Workaround | Source |
|------------|--------|---------------|--------|
| Type hints limited to `str`, `int`, `float`, `bool` | `KeyError: 'type'` with complex types (`Optional`, `Dict`, `List`, `Union`) | Simplify all signatures to the 4 primitives | Discussion #13174 |
| Async tools expose sensitive data via `functools.partial` | API keys, passwords visible in pipe logs | Manually filter data before external sending | Issue #16307 |
| Native tool calling unreliable with small models | Model doesn't process tool result | Use frontier models or Default mode | Issue #9414 |
| Multiple citations merged | Distinct citations aggregated into one | Use truly distinct IDs (grouping mechanism not clarified) | Issue #17366 |
| Event emitter/call unavailable for external tools (OpenAPI/MCP) | No real-time feedback from external tools | Use REST endpoint `/api/v1/chats/{chat_id}/messages/{message_id}/event` | Issue #20892 |
| System prompt duplication during agentic tool calls | Token waste, cache extra cost | Not documented | Issue #19169 |
| `outlet()` not called for direct API requests | No post-processing for API clients | Manually call `POST /api/chat/completed` | Official doc (Filter) |
| Message events broken in Native mode | `message`, `replace`, `chat:message:delta` overwritten by server snapshots | Use only `status`, `citation`, `notification` in Native mode | Official doc (Tools dev) |

## Feature Requests Revealing Limitations

| Feature Request | Implication | Source |
|-----------------|-------------|--------|
| SSE support for agentic server status events | External servers cannot natively update status | Issue #19250 |
| Simplification of Tools/Functions ecosystem | Taxonomy confusion recognized by community | Discussion #16415 |
| Scheduled background tasks | No native support for scheduled functions | Discussion #15832 |
| Native MCP with tool management | MCP integration still evolving | Discussion #16238 |

---

## Community Repositories

### owndev/Open-WebUI-Functions

- **URL:** https://github.com/owndev/Open-WebUI-Functions
- **Stars:** 336 / **Forks:** 51
- **License:** Apache 2.0
- **Description:** Collection of pipelines, filters and integrations (Azure AI, N8N, Google Gemini, Infomaniak)

**Structure:**
```
├── docs/
│   ├── azure-ai-citations.md
│   ├── google-gemini-integration.md
│   ├── n8n-integration.md
│   └── ...
├── filters/
│   ├── google_search_tool.py
│   ├── time_token_tracker.py
│   └── vertex_ai_search_tool.py
└── pipelines/
    ├── azure/
    ├── google/
    ├── infomaniak/
    └── n8n/
```

**Observed patterns:** Configuration via environment variables with provider prefixes, automatic encryption of sensitive data (prefix `encrypted:` in valves), systematic streaming/non-streaming support, token tracking via metadata.

### Haervwe/open-webui-tools

- **URL:** https://github.com/Haervwe/open-webui-tools
- **Required version:** Open WebUI 0.6.0+ / Python 3.8+
- **License:** MIT
- **Description:** Modular toolkit: 20+ tools, pipes and filters

**Notable tools:**

| Type | Examples |
|------|---------|
| Tools | arXiv Search, Perplexica Search, Pexels Media, YouTube, SearxNG Images, Image Generators (Native/HF/Cloudflare/ComfyUI), Video (ComfyUI/Google Veo), OpenWeatherMap |
| Pipes | Planner Agent v3, Letta Agent, arXiv Research MCTS, Multi Model Conversations v2, Resume Analyzer, Perplexica Pipe, MiniMax LLM Pipe |
| Filters | Doodle Paint, Prompt Enhancer, Semantic Router, Full Document, Clean Thinking Tags, OpenRouter WebSearch Citations |

**Observed patterns:** `self.citation = True`, real-time event emission, user-friendly error handling, tool chaining in Pipes, multi-agent delegation.

### open-webui/pipelines (official)

- **URL:** https://github.com/open-webui/pipelines
- **Examples:** `examples/` with subfolders `filters/` (16 files), `pipelines/` (integrations, providers, rag), `scaffolds/` (4 templates)

**Example filters (16):**

1. conversation_turn_limit_filter.py
2. datadog_filter_pipeline.py
3. detoxify_filter_pipeline.py
4. dynamic_ollama_vision_filter_pipeline.py
5. function_calling_filter_pipeline.py
6. google_translation_filter_pipeline.py
7. home_assistant_filter.py
8. langfuse_filter_pipeline.py
9. langfuse_v3_filter_pipeline.py
10. libretranslate_filter_pipeline.py
11. llm_translate_filter_pipeline.py
12. llmguard_prompt_injection_filter_pipeline.py
13. mem0_memory_filter_pipeline.py
14. opik_filter_pipeline.py
15. presidio_filter_pipeline.py (PII anonymization)
16. rate_limit_filter_pipeline.py

**Scaffolds (4):**

1. example_pipeline_scaffold.py — Basic pipeline with lifecycle hooks
2. filter_pipeline_scaffold.py — Filter with `pipelines` valve and `self.type = "filter"`
3. function_calling_scaffold.py — Pipeline with function calling support (`self.type = "manifold"`)
4. manifold_pipeline_scaffold.py — Manifold with multiple sub-models

> See [03-architecture-lifecycle.md](03-architecture-lifecycle.md) for scaffold source code.

### open-webui/openapi-servers (official)

- **URL:** https://github.com/open-webui/openapi-servers
- **Description:** Reference OpenAPI tool servers (filesystem, memory, time)
- **License:** MIT

### pahautelman/open-webui-tool-skeleton

- **URL:** https://github.com/pahautelman/open-webui-tool-skeleton
- **Stars:** 10 / **Forks:** 2
- **License:** MIT
- **Description:** Foundational template with EventEmitter helper class

> See [14-development-debugging.md](14-development-debugging.md) for template code.

## Community Library

- **URL:** https://openwebui.com/functions
- **Volume:** 541 unique functions, 276 unique tools (secondary sources)
- **Status at time of collection:** HTTP 403 on all tested pages

## Not Collected Data

| Data | Status | Comment |
|------|--------|-------------|
| Discord Open WebUI | Inaccessible | Requires authentication, ephemeral non-indexable content |
| Medium article "Beyond Text" (full content) | Paywall | Only metadata and table of contents collected. Personal blog on 404. |
| Content of pipelines/examples/pipelines/ subfolders | Structure identified | Source code not extracted in detail |
| Complete releases changelog | Not collected | v0.8.12 identified but detailed changelog not traversed |

## Known Collection Gaps

| Source | Gap | Impact |
|--------|--------|--------|
| DeepWiki (AI source) | exec/eval mechanism, hot-reload, error handling, versioning | Not verifiable — see warning in 03-architecture-lifecycle.md |
| Medium article "Beyond Text" | Complete technical content | Paywall — not collectable, only metadata and table of contents available |
| open-webui/openapi-servers | Server content (filesystem, memory) | Only the time server documented in quickstart |
| Issue #11750 | Complete details | Marked as unresolved, partially collected context |
| owndev/Open-WebUI-Functions | Azure AI patterns, key encryption, BM25+semantic rerank | High-level summary only — specific patterns not detailed |
| Haervwe/open-webui-tools | Planner Agent v3, Letta Agent architecture | Names listed but architecture not detailed |
