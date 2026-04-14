# Introduction — Développer des extensions pour Open WebUI

## Objectif de cette documentation

Ce corpus documentaire couvre **tout ce qu'il faut savoir pour coder des tools, functions et pipelines** pour Open WebUI. Il est conçu comme une référence pratique pour les développeurs qui veulent créer, déployer et maintenir des extensions custom.

## Public cible

Développeurs Python souhaitant étendre Open WebUI avec des outils personnalisés, des modèles custom, des filtres de pré/post-traitement, des actions interactives, ou des intégrations externes (OpenAPI/MCP).

Prérequis : maîtrise de Python (async/await, pydantic, type hints), familiarité avec les API REST et le function calling des LLMs.

## Version couverte

**Open WebUI v0.8.12** (publiée le 27 mars 2025). Les informations de migration vers v0.5.0 et v0.9.0 sont documentées dans la section [15-migrations.md](15-migrations.md).

> Open WebUI évolue rapidement. Chaque affirmation technique est rattachée à sa source (URL + date de consultation). Vérifiez la correspondance avec votre version déployée.

## Conventions de notation

- Les noms de paramètres injectés sont écrits avec double underscore : `__event_emitter__`, `__user__`, etc.
- Les extraits de code sont en Python sauf indication contraire.
- Les tableaux "Source" indiquent l'URL d'origine et la date de consultation.
- Les sections "Leçon pour le corpus" signalent les enseignements tirés des bugs et discussions communautaires.

## Sources consultées

| # | Source | URL | Fiabilité |
|---|--------|-----|-----------|
| 1 | Documentation officielle Open WebUI | https://docs.openwebui.com/features/extensibility/plugin/ | Primaire |
| 2 | Code source open-webui/open-webui | https://github.com/open-webui/open-webui | Primaire |
| 3 | Doc Events & Plugin Development | https://docs.openwebui.com/features/extensibility/plugin/development/events | Primaire |
| 4 | Pages Pipe/Action/Filter | Voir URLs dans chaque section | Primaire |
| 5 | Dépôt docs (sources MDX) | https://github.com/open-webui/docs | Primaire |
| 6 | DeepWiki Functions System | https://deepwiki.com/open-webui/docs/4.2-functions-system | Complémentaire (IA-généré) |
| 7 | Bibliothèque communautaire | https://openwebui.com/functions | Variable (403 au moment de la collecte) |
| 8 | Issues/Discussions GitHub | https://github.com/open-webui/open-webui/issues | Communauté |
| 9 | Tool skeleton template | https://github.com/pahautelman/open-webui-tool-skeleton | Communauté |
| 10 | Articles Medium/Blogs | Variables | Éditorial |
| 11 | Discord Open WebUI | https://discord.com/invite/5rJgQTnV4s | Informel |

**Date de collecte :** 13 avril 2026

## Structure du corpus

| Fichier | Sujet |
|---------|-------|
| [02-extension-taxonomy.md](02-extension-taxonomy.md) | Taxonomie complète des types d'extensions |
| [03-architecture-lifecycle.md](03-architecture-lifecycle.md) | Architecture technique et cycle de vie |
| [04-reserved-parameters.md](04-reserved-parameters.md) | Référence des paramètres injectés |
| [05-valves.md](05-valves.md) | Système de Valves et UserValves |
| [06-event-system.md](06-event-system.md) | Système d'événements (emitter + call) |
| [07-tools.md](07-tools.md) | Créer un Tool |
| [08-pipes.md](08-pipes.md) | Créer un Pipe |
| [09-filters.md](09-filters.md) | Créer un Filter |
| [10-actions.md](10-actions.md) | Créer une Action |
| [11-rich-ui.md](11-rich-ui.md) | Rich UI Embedding |
| [12-external-tools.md](12-external-tools.md) | Outils externes (OpenAPI + MCP) |
| [13-security.md](13-security.md) | Sécurité et bonnes pratiques |
| [14-development-debugging.md](14-development-debugging.md) | Développement et débogage |
| [15-migrations.md](15-migrations.md) | Migrations et breaking changes |
| [16-known-issues-resources.md](16-known-issues-resources.md) | Problèmes connus et ressources communautaires |
