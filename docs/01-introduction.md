# Introduction — Developing Extensions for Open WebUI

## Purpose of this Documentation

This documentation covers **everything you need to know to code tools, functions, and pipelines** for Open WebUI. It is designed as a practical reference for developers who want to create, deploy, and maintain custom extensions.

## Target Audience

Python developers wishing to extend Open WebUI with custom tools, custom models, pre/post-processing filters, interactive actions, or external integrations (OpenAPI/MCP).

Prerequisites: mastery of Python (async/await, pydantic, type hints), familiarity with REST APIs and LLM function calling.

## Version Covered

**Open WebUI v0.8.12** (released March 27, 2025). Migration information to v0.5.0 and v0.9.0 is documented in [15-migrations.md](15-migrations.md).

> Open WebUI evolves rapidly. Each technical statement is tied to its source (URL + date of consultation). Verify correspondence with your deployed version.

## Notation Conventions

- Injected parameter names are written with double underscore: `__event_emitter__`, `__user__`, etc.
- Code snippets are in Python unless otherwise indicated.
- "Source" tables indicate the original URL and date of consultation.
- "Lesson for the corpus" sections signal insights gained from bugs and community discussions.

## Sources Consulted

| # | Source | URL | Reliability |
|---|--------|-----|-------------|
| 1 | Open WebUI Official Documentation | https://docs.openwebui.com/features/extensibility/plugin/ | Primary |
| 2 | open-webui/open-webui Source Code | https://github.com/open-webui/open-webui | Primary |
| 3 | Events & Plugin Development Doc | https://docs.openwebui.com/features/extensibility/plugin/development/events | Primary |
| 4 | Pipe/Action/Filter Pages | See URLs in each section | Primary |
| 5 | docs repo (MDX sources) | https://github.com/open-webui/docs | Primary |
| 6 | DeepWiki Functions System | https://deepwiki.com/open-webui/docs/4.2-functions-system | Supplementary (AI-generated) |
| 7 | Community Library | https://openwebui.com/functions | Variable (403 at time of collection) |
| 8 | GitHub Issues/Discussions | https://github.com/open-webui/open-webui/issues | Community |
| 9 | Tool skeleton template | https://github.com/pahautelman/open-webui-tool-skeleton | Community |
| 10 | Medium Articles/Blogs | Variable | Editorial |
| 11 | Open WebUI Discord | https://discord.com/invite/5rJgQTnV4s | Informal |

**Date of collection:** April 13, 2026

## Corpus Structure

| File | Topic |
|------|-------|
| [02-extension-taxonomy.md](02-extension-taxonomy.md) | Complete taxonomy of extension types |
| [03-architecture-lifecycle.md](03-architecture-lifecycle.md) | Technical architecture and lifecycle |
| [04-reserved-parameters.md](04-reserved-parameters.md) | Reference of injected parameters |
| [05-valves.md](05-valves.md) | Valve system and UserValves |
| [06-event-system.md](06-event-system.md) | Event system (emitter + call) |
| [07-tools.md](07-tools.md) | Creating a Tool |
| [08-pipes.md](08-pipes.md) | Creating a Pipe |
| [09-filters.md](09-filters.md) | Creating a Filter |
| [10-actions.md](10-actions.md) | Creating an Action |
| [11-rich-ui.md](11-rich-ui.md) | Rich UI Embedding |
| [12-external-tools.md](12-external-tools.md) | External tools (OpenAPI + MCP) |
| [13-security.md](13-security.md) | Security and best practices |
| [14-development-debugging.md](14-development-debugging.md) | Development and debugging |
| [15-migrations.md](15-migrations.md) | Migrations and breaking changes |
| [16-known-issues-resources.md](16-known-issues-resources.md) | Known issues and community resources |
