# Problèmes connus et ressources communautaires

## Bugs résolus (pour contexte historique)

| Bug | Version | Impact | Résolution | Issue |
|-----|---------|--------|------------|-------|
| `__event_emitter__` cassé dans outlet | v0.5.2 | Pas d'émission d'événements depuis les filtres outlet | PR #8159 | #8168 |
| `__event_emitter__` cassé dans Actions | ~v0.5.x | Exception `user_id` dans les Actions | PR #8246 | #8292 |
| Caractères corrompus dans status | v0.5.0+ | Descriptions de status illisibles via i18n | Non documenté | #8129 |
| Contenu outlet non persisté | v0.5.2 | Modifications outlet annulées après render | PR #8159 | #8168 |
| `__event_emitter__` erreur pipe function | Mars 2025 | Erreurs lors de l'appel dans les pipes | Non résolu (?) | #11750 |

## Limitations actuelles non résolues

| Limitation | Impact | Contournement | Source |
|------------|--------|---------------|--------|
| Type hints limités à `str`, `int`, `float`, `bool` | `KeyError: 'type'` avec types complexes (`Optional`, `Dict`, `List`, `Union`) | Simplifier toutes les signatures aux 4 primitifs | Discussion #13174 |
| Async tools exposent données sensibles via `functools.partial` | Clés API, mots de passe visibles dans les logs de pipe | Filtrer manuellement les données avant envoi externe | Issue #16307 |
| Native tool calling peu fiable avec petits modèles | Modèle ne traite pas le résultat du tool | Utiliser modèles frontier ou mode Default | Issue #9414 |
| Citations multiples fusionnées | Citations distinctes agrégées en une seule | Utiliser des IDs vraiment distincts (mécanisme de groupement non clarifié) | Issue #17366 |
| Event emitter/call indisponible pour outils externes (OpenAPI/MCP) | Pas de feedback temps réel depuis outils externes | Utiliser REST endpoint `/api/v1/chats/{chat_id}/messages/{message_id}/event` | Issue #20892 |
| Duplication system prompt lors des tool calls agentic | Gaspillage de tokens, surcoût cache | Non documenté | Issue #19169 |
| `outlet()` non appelé pour requêtes API directes | Pas de post-traitement pour clients API | Appeler manuellement `POST /api/chat/completed` | Doc officielle (Filter) |
| Message events cassés en mode Native | `message`, `replace`, `chat:message:delta` écrasés par les snapshots serveur | Utiliser uniquement `status`, `citation`, `notification` en mode Native | Doc officielle (Tools dev) |

## Demandes de fonctionnalités révélant les limites

| Feature request | Implication | Source |
|-----------------|-------------|--------|
| Support SSE pour status events des serveurs agentic | Les serveurs externes ne peuvent pas mettre à jour le status nativement | Issue #19250 |
| Simplification de l'écosystème Tools/Functions | Confusion taxonomique reconnue par la communauté | Discussion #16415 |
| Tâches planifiées en arrière-plan | Pas de support natif pour les fonctions programmées | Discussion #15832 |
| MCP natif avec gestion des tools | Intégration MCP encore en évolution | Discussion #16238 |

---

## Dépôts communautaires

### owndev/Open-WebUI-Functions

- **URL :** https://github.com/owndev/Open-WebUI-Functions
- **Stars :** 336 / **Forks :** 51
- **Licence :** Apache 2.0
- **Description :** Collection de pipelines, filtres et intégrations (Azure AI, N8N, Google Gemini, Infomaniak)

**Structure :**
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

**Patterns observés :** Configuration par variables d'environnement avec préfixes provider, chiffrement automatique des données sensibles (préfixe `encrypted:` dans les valves), support streaming/non-streaming systématique, token tracking via métadonnées.

### Haervwe/open-webui-tools

- **URL :** https://github.com/Haervwe/open-webui-tools
- **Version requise :** Open WebUI 0.6.0+ / Python 3.8+
- **Licence :** MIT
- **Description :** Toolkit modulaire : 20+ outils, pipes et filtres

**Outils notables :**

| Type | Exemples |
|------|---------|
| Tools | arXiv Search, Perplexica Search, Pexels Media, YouTube, SearxNG Images, Image Generators (Native/HF/Cloudflare/ComfyUI), Video (ComfyUI/Google Veo), OpenWeatherMap |
| Pipes | Planner Agent v3, Letta Agent, arXiv Research MCTS, Multi Model Conversations v2, Resume Analyzer, Perplexica Pipe, MiniMax LLM Pipe |
| Filters | Doodle Paint, Prompt Enhancer, Semantic Router, Full Document, Clean Thinking Tags, OpenRouter WebSearch Citations |

**Patterns observés :** `self.citation = True`, émission d'événements temps réel, gestion d'erreurs user-friendly, chaînage d'outils dans les Pipes, délégation multi-agents.

### open-webui/pipelines (officiel)

- **URL :** https://github.com/open-webui/pipelines
- **Exemples :** `examples/` avec sous-dossiers `filters/` (16 fichiers), `pipelines/` (integrations, providers, rag), `scaffolds/` (4 templates)

**Filtres exemples (16) :**

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
15. presidio_filter_pipeline.py (anonymisation PII)
16. rate_limit_filter_pipeline.py

**Scaffolds (4) :**

1. example_pipeline_scaffold.py — Pipeline basique avec lifecycle hooks
2. filter_pipeline_scaffold.py — Filtre avec valve `pipelines` et `self.type = "filter"`
3. function_calling_scaffold.py — Pipeline avec support function calling (`self.type = "manifold"`)
4. manifold_pipeline_scaffold.py — Manifold avec sous-modèles multiples

> Voir [03-architecture-lifecycle.md](03-architecture-lifecycle.md) pour le code source des scaffolds.

### open-webui/openapi-servers (officiel)

- **URL :** https://github.com/open-webui/openapi-servers
- **Description :** Serveurs d'outils OpenAPI de référence (filesystem, memory, time)
- **Licence :** MIT

### pahautelman/open-webui-tool-skeleton

- **URL :** https://github.com/pahautelman/open-webui-tool-skeleton
- **Stars :** 10 / **Forks :** 2
- **Licence :** MIT
- **Description :** Template fondationnel avec classe EventEmitter helper

> Voir [14-development-debugging.md](14-development-debugging.md) pour le code du template.

## Bibliothèque communautaire

- **URL :** https://openwebui.com/functions
- **Volume :** 541 fonctions uniques, 276 outils uniques (sources secondaires)
- **Statut au moment de la collecte :** HTTP 403 sur toutes les pages testées

## Données non collectées

| Donnée | Statut | Commentaire |
|--------|--------|-------------|
| Discord Open WebUI | Inaccessible | Requiert authentification, contenu éphémère non indexable |
| Article Medium "Beyond Text" (contenu complet) | Paywall | Seuls métadonnées et sommaire collectés. Blog personnel en 404. |
| Contenu des sous-dossiers pipelines/examples/pipelines/ | Structure identifiée | Code source non extrait en détail |
| Changelog complet des releases | Non collecté | v0.8.12 identifiée mais changelog détaillé non parcouru |

## Lacunes de collecte connues

| Source | Lacune | Impact |
|--------|--------|--------|
| DeepWiki (source IA) | Mécanisme exec/eval, hot-reload, gestion erreurs, versionnage | Non vérifiable — voir avertissement dans 03-architecture-lifecycle.md |
| Article Medium "Beyond Text" | Contenu technique complet | Paywall — non collectable, seuls métadonnées et sommaire disponibles |
| open-webui/openapi-servers | Contenu des serveurs (filesystem, memory) | Seul le time server est documenté en quickstart |
| Issue #11750 | Détails complets | Marquée comme non résolu, contexte partiellement collecté |
| owndev/Open-WebUI-Functions | Patterns Azure AI, chiffrement clés, BM25+semantic rerank | Résumé haut niveau uniquement — les patterns spécifiques ne sont pas détaillés |
| Haervwe/open-webui-tools | Architecture Planner Agent v3, Letta Agent | Noms listés mais architecture non détaillée |
