# Corpus documentaire — Open WebUI : Création d'outils custom
## LOT 2 : Sources 5 à 7 (Dépôt docs GitHub, DeepWiki, Bibliothèque communautaire)

**Version cible :** Open WebUI v0.8.12 (publiée le 27 mars 2025)
**Date de collecte :** 13 avril 2026

---

# SOURCE 5 : DÉPÔT GITHUB open-webui/docs

**URL :** https://github.com/open-webui/docs
**Ce qu'on y cherche :** Sources Markdown de la documentation, modifications récentes, sections en cours de rédaction.

## 5.1 Structure du dépôt documentaire

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Structure plugin | `docs/features/extensibility/plugin/` contient : `index.mdx`, sous-dossiers `development/`, `functions/`, `migration/`, `tools/` | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin | consultée le 13/04/2026 |
| Fichiers development | `_category_.json`, `events.mdx`, `reserved-args.mdx`, `rich-ui.mdx`, `valves.mdx` | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin/development | consultée le 13/04/2026 |
| Fichiers functions | `action.mdx`, `filter.mdx`, `index.mdx`, `pipe.mdx` | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin/functions | consultée le 13/04/2026 |
| Fichiers tools | `index.mdx`, `development.mdx`, sous-dossier `openapi-servers/` | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin/tools | consultée le 13/04/2026 |
| Hiérarchie parente | `docs/features/extensibility/` contient aussi `pipelines/`, `mcp.mdx`, `_category_.json` | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin | consultée le 13/04/2026 |
| Format | Tous les fichiers sont en MDX (Markdown + JSX) | https://github.com/open-webui/docs/tree/main/docs/features/extensibility/plugin | consultée le 13/04/2026 |

### Contenu détaillé — Observations sur le dépôt :

La documentation est organisée de manière modulaire avec un fichier MDX par concept (un par type de fonction, un par aspect du développement). Le format MDX permet d'inclure des composants interactifs React dans la documentation.

**Pages identifiées dans le dépôt mais pas encore consultées au Lot 1 :** `mcp.mdx` (documentation MCP), contenu du sous-dossier `openapi-servers/`.

**Limites constatées :** Les timestamps de modification ne sont pas directement visibles depuis l'interface GitHub directory listing. Il faudrait consulter le git log pour identifier les modifications récentes. Le contenu des fichiers MDX confirme les données déjà collectées au Lot 1 — pas de sections en brouillon ou de contenu non déployé identifié.

## 5.2 Contenu brut des fichiers MDX (recoupement avec Lot 1)

| Fichier | Concordance avec doc live | Écarts identifiés | URL source |
|---------|---------------------------|-------------------|------------|
| `valves.mdx` | ✅ Concordance complète avec la page live | Aucun écart détecté | https://raw.githubusercontent.com/open-webui/docs/main/docs/features/extensibility/plugin/development/valves.mdx |
| `reserved-args.mdx` | ✅ Concordance complète avec la page live | Aucun écart détecté | https://raw.githubusercontent.com/open-webui/docs/main/docs/features/extensibility/plugin/development/reserved-args.mdx |
| `events.mdx` | ✅ Contenu identique à la page live (accès réussi via URL sans slash final) | Aucun écart détecté | https://raw.githubusercontent.com/open-webui/docs/main/docs/features/extensibility/plugin/development/events.mdx |

**Conclusion Source 5 :** La documentation live est à jour par rapport aux sources Markdown du dépôt. Pas de brouillons en cours de rédaction identifiés. Le recoupement confirme la fiabilité des données collectées au Lot 1.

---

# SOURCE 6 : DEEPWIKI — Functions System Overview

**URL :** https://deepwiki.com/open-webui/docs/4.2-functions-system
**Ce qu'on y cherche :** Vue d'architecture générée automatiquement, complément à la doc officielle.
**Limites :** Source générée par IA — à recouper systématiquement.

## 6.1 Architecture du Functions System (vue DeepWiki)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Types de fonctions et contexte d'exécution | Pipe: "Create custom models/agents" avec "full request/response control". Filter: "pre/post-processing hooks" comme middleware. Action: "Add UI interactions" via "buttons under chat messages". | https://deepwiki.com/open-webui/docs/4.2-functions-system | consultée le 13/04/2026 |
| Flux de données | `User Input → Inlet Filters → RAG Query → LLM Call → Outlet Filters → UI Display` | https://deepwiki.com/open-webui/docs/4.2-functions-system | consultée le 13/04/2026 |
| Manifold Pattern | Pipes peuvent exposer plusieurs modèles via `pipes()` retournant une liste de dictionnaires modèle. Permet des patterns proxy vers APIs externes. | https://deepwiki.com/open-webui/docs/4.2-functions-system | consultée le 13/04/2026 |
| Modèle de sécurité | Admin : contrôle complet du cycle de vie. User : peut seulement utiliser les fonctions activées par l'admin, ne peut pas voir le code source Python. Pending : aucun accès. | https://deepwiki.com/open-webui/docs/4.2-functions-system | consultée le 13/04/2026 |

### Contenu détaillé — Flux de données complet :
```
User Input → Inlet Filters → RAG Query → LLM Call → Outlet Filters → UI Display
                ↓                                          ↓
           Pré-traitement                         Post-traitement
```

### Contenu détaillé — Données NON trouvées dans DeepWiki :

Les éléments suivants sont absents de la page DeepWiki (listés explicitement comme "not in official docs" par la source elle-même) :

- Mécanisme d'implémentation exec/eval réel
- Procédures de découverte et chargement dynamique des fonctions
- Logique de sérialisation/validation des Valves/UserValves
- Spécificités du sandboxing et de la gestion d'erreurs
- Hooks de profilage de performance
- Hooks de cycle de vie (initialisation, shutdown)
- Gestion de l'exécution concurrente sur plusieurs workers
- Mécanismes de versionnage/compatibilité des fonctions
- Détails du hot-reload

**Évaluation de la source :** DeepWiki fournit un schéma de flux de données utile mais n'apporte pas de données techniques absentes de la documentation officielle. Sa valeur est principalement illustrative (schéma du pipeline) et confirmative (recoupement des rôles des 3 sous-types). Aucune information erronée détectée par recoupement avec le code source.

---

# SOURCE 7 : BIBLIOTHÈQUE COMMUNAUTAIRE ET DÉPÔTS GITHUB TIERS

**URL principale :** https://openwebui.com/functions (inaccessible — HTTP 403)
**URLs alternatives utilisées :** GitHub repos communautaires et discussions

## 7.1 Accès à la bibliothèque communautaire

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Statut bibliothèque | HTTP 403 — accès refusé lors de la collecte | https://openwebui.com/functions | consultée le 13/04/2026 |
| Pages individuelles | HTTP 403 sur toutes les pages testées (hub/custom_action, hub/autotool_filter, podden/anthropic_pipe) | https://openwebui.com/f/hub/custom_action | consultée le 13/04/2026 |
| Volume communautaire | 541 fonctions uniques et 276 outils uniques référencés (d'après sources secondaires) | Recherche web | consultée le 13/04/2026 |

**Stratégie de contournement :** Collecte via les dépôts GitHub communautaires et les discussions publiques.

## 7.2 Dépôt communautaire owndev/Open-WebUI-Functions

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Description | Collection de pipelines, filtres et intégrations custom pour Open WebUI (Azure AI, N8N, Google Gemini, Infomaniak) | https://github.com/owndev/Open-WebUI-Functions | consultée le 13/04/2026 |
| Stars / Forks | 336 stars, 51 forks | https://github.com/owndev/Open-WebUI-Functions | consultée le 13/04/2026 |
| Licence | Apache 2.0 | https://github.com/owndev/Open-WebUI-Functions | consultée le 13/04/2026 |
| Nombre de fonctions | 8+ (4 pipelines + 3+ filtres + intégrations) | https://github.com/owndev/Open-WebUI-Functions | consultée le 13/04/2026 |

### Contenu détaillé — Structure du dépôt :
```
.
├── docs/                          # Documentation par intégration
│   ├── azure-ai-citations.md
│   ├── azure-ai-integration.md
│   ├── google-gemini-integration.md
│   ├── infomaniak-integration.md
│   ├── n8n-integration.md
│   ├── n8n-tool-usage-display.md
│   └── setup-azure-log-analytics.md
├── filters/
│   ├── google_search_tool.py      # Grounding via Google Search
│   ├── time_token_tracker.py      # Temps de réponse et tokens
│   └── vertex_ai_search_tool.py   # Grounding via Vertex AI
└── pipelines/
    ├── azure/                     # Azure AI Foundry Pipeline
    ├── google/                    # Google Gemini Pipeline
    ├── infomaniak/                # Infomaniak Pipeline
    └── n8n/                       # N8N Workflow Pipeline
```

### Contenu détaillé — Pipelines :

**Azure AI Foundry Pipeline (`pipelines/azure/azure_ai_foundry.py`) :**
- Intégration Azure OpenAI + Azure AI models
- Azure Search/RAG avec citations natives et scores de pertinence (BM25 keyword + semantic rerank)
- Support multi-modèles via configuration séparée par point-virgule/virgule
- Catalogue prédéfini : GPT-4o, GPT-5, o3, o4-mini, Phi-4, DeepSeek-R1/V3, Mistral, Llama 3.x, Cohere, Grok
- Auth flexible : `api-key` header ou `Authorization: Bearer` token
- Token tracking via `stream_options.include_usage`
- Chiffrement des clés API (requiert `WEBUI_SECRET_KEY`)

**N8N Pipeline (`pipelines/n8n/n8n.py`) :**
- Intégration workflow automation N8N
- Affichage de l'usage des outils AI agent (v2.2.0) avec 3 niveaux de verbosité
- Streaming et non-streaming
- Webhooks dynamiques

**Google Gemini Pipeline (`pipelines/google/google_gemini.py`) :**
- Support Google Generative AI API et Vertex AI API
- Modes thinking/reasoning configurables
- Traitement image avancé (compression, redimensionnement, déduplication par hash)
- Génération d'images (Gemini 3) et vidéos (Veo 3.1, 3, 2)
- Grounding via Google Search et Vertex AI Search
- Tool calling natif
- Overrides UserValves par utilisateur

### Contenu détaillé — Filtres :

**Time Token Tracker (`filters/time_token_tracker.py`) :**
- Mesure temps de réponse et usage tokens par interaction
- Utilise `tiktoken` d'OpenAI (précis uniquement pour modèles OpenAI)
- Intégration optionnelle Azure Log Analytics

### Contenu détaillé — Patterns architecturaux observés :
- Configuration par variables d'environnement avec préfixes par provider (`AZURE_`, `GOOGLE_`, `N8N_`)
- Chiffrement automatique des données sensibles (prefix `encrypted:`)
- Support streaming et non-streaming systématique
- Token tracking via métadonnées de réponse
- Gestion d'erreurs avec timeouts configurables

**Source :** https://github.com/owndev/Open-WebUI-Functions — consultée le 13/04/2026

## 7.3 Dépôt communautaire Haervwe/open-webui-tools

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Description | Toolkit modulaire : 20+ outils, pipes et filtres. Recherche académique, agents autonomes, créativité multimodale | https://github.com/Haervwe/open-webui-tools | consultée le 13/04/2026 |
| Version Open WebUI requise | 0.6.0+ recommandé | https://github.com/Haervwe/open-webui-tools | consultée le 13/04/2026 |
| Licence | MIT | https://github.com/Haervwe/open-webui-tools | consultée le 13/04/2026 |
| Python | 3.8+ | https://github.com/Haervwe/open-webui-tools | consultée le 13/04/2026 |

### Contenu détaillé — Inventaire complet des outils :

**TOOLS (fonctions standalone appelées par le LLM) :**

| Outil | Catégorie | API requise |
|-------|-----------|-------------|
| arXiv Search | Recherche académique | Non |
| Perplexica Search | Recherche web avec citations | Oui (Perplexica) |
| Pexels Media Search | Photos/vidéos stock | Oui (Pexels) |
| YouTube Search & Embed | Vidéo | Oui (YouTube) |
| SearxNG Image Search | Recherche images décentralisée | Oui (SearxNG) |
| Native Image Generator | Génération images | Non (built-in) |
| Hugging Face Image Generator | Génération images | Oui (HF) |
| Cloudflare Workers AI Image Generator | Génération images | Oui (Cloudflare) |
| ComfyUI Image-to-Image | Édition images | Oui (ComfyUI) |
| Flux Kontext ComfyUI | Édition images pro | Oui (ComfyUI) |
| ComfyUI ACE Step 1.5 Audio | Génération musique | Oui (ComfyUI) |
| ComfyUI Text-to-Video | Création vidéo | Oui (ComfyUI) |
| Google Veo Text/Image-to-Video | Création vidéo | Oui (Google) |
| OpenWeatherMap Forecast | Météo widget | Oui (OWM) |

**FUNCTION PIPES (workflows multi-étapes) :**

| Pipe | Catégorie |
|------|-----------|
| Planner Agent v3 | Agent autonome avec planning, délégation, suivi visuel |
| Letta Agent | Intégration agent autonome |
| arXiv Research MCTS | Recherche Monte Carlo Tree Search |
| Multi Model Conversations v2 | Discussions multi-agents avec UI interactive |
| Resume Analyzer | Analyse de CV professionnelle |
| Mopidy Music Controller | Contrôle serveur musique |
| Perplexica Pipe | Recherche web streaming avec citations |
| MiniMax LLM Pipe | Routage vers API MiniMax (contexte 204K) |

**FILTERS (pré/post-traitement) :**

| Filtre | Fonction |
|--------|----------|
| Doodle Paint | Canvas de dessin avant soumission |
| Prompt Enhancer | Amélioration automatique des prompts |
| Semantic Router | Sélection intelligente de modèle |
| Full Document | Traitement de fichiers |
| Clean Thinking Tags | Nettoyage de conversation |
| OpenRouter WebSearch Citations | Recherche web avec gestion citations |

### Contenu détaillé — Patterns architecturaux observés :
- Pattern `Tools` class avec Valves (BaseModel/Field)
- Émission d'événements pour mises à jour en temps réel
- Gestion d'erreurs avec messages user-friendly
- Chaînage d'outils dans les Pipes
- Délégation multi-agents dans les agents autonomes
- Composants UI interactifs
- Limitation des résultats pour ne pas surcharger le LLM
- Support `self.citation = True` pour afficher le contexte des outils

**Source :** https://github.com/Haervwe/open-webui-tools — consultée le 13/04/2026

## 7.4 Exemples officiels du dépôt open-webui/pipelines

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Structure exemples | 3 dossiers : `filters/`, `pipelines/`, `scaffolds/` | https://github.com/open-webui/pipelines/tree/main/examples | consultée le 13/04/2026 |
| Nombre filtres exemples | 16 fichiers | https://github.com/open-webui/pipelines/tree/main/examples/filters | consultée le 13/04/2026 |
| Nombre scaffolds | 4 templates | https://github.com/open-webui/pipelines/tree/main/examples/scaffolds | consultée le 13/04/2026 |
| Sous-dossiers pipelines | `integrations/`, `providers/`, `rag/`, + `events_pipeline.py` | https://github.com/open-webui/pipelines/tree/main/examples/pipelines | consultée le 13/04/2026 |

### Contenu détaillé — Filtres exemples officiels (16 fichiers) :

1. `conversation_turn_limit_filter.py` — Limite de tours de conversation
2. `datadog_filter_pipeline.py` — Monitoring Datadog
3. `detoxify_filter_pipeline.py` — Filtrage contenu toxique
4. `dynamic_ollama_vision_filter_pipeline.py` — Vision dynamique Ollama
5. `function_calling_filter_pipeline.py` — Pipeline de function calling
6. `google_translation_filter_pipeline.py` — Traduction Google
7. `home_assistant_filter.py` — Intégration domotique
8. `langfuse_filter_pipeline.py` — Observabilité Langfuse
9. `langfuse_v3_filter_pipeline.py` — Observabilité Langfuse v3
10. `libretranslate_filter_pipeline.py` — Traduction LibreTranslate
11. `llm_translate_filter_pipeline.py` — Traduction via LLM
12. `llmguard_prompt_injection_filter_pipeline.py` — Protection injection de prompts
13. `mem0_memory_filter_pipeline.py` — Mémoire persistante Mem0
14. `opik_filter_pipeline.py` — Observabilité Opik
15. `presidio_filter_pipeline.py` — Anonymisation PII (Microsoft Presidio)
16. `rate_limit_filter_pipeline.py` — Limitation de débit

### Contenu détaillé — Scaffolds (templates de démarrage) :

1. `example_pipeline_scaffold.py` — Template pipeline basique
2. `filter_pipeline_scaffold.py` — Template filtre
3. `function_calling_scaffold.py` — Template function calling
4. `manifold_pipeline_scaffold.py` — Template manifold (multi-modèles)

**Source :** https://github.com/open-webui/pipelines/tree/main/examples — consultée le 13/04/2026

## 7.5 Guide d'utilisation des Tools (Discussion GitHub #3134)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Définition Tools vs Pipelines | "Tools are a subset of the capabilities of a full pipeline. Quick and easy to get started with, but potentially limited in their use-cases, and certainly only usable in WebUI." | https://github.com/open-webui/open-webui/discussions/3134 | consultée le 13/04/2026 |
| Exigence docstrings | CRITIQUE : docstrings et type hints manquants provoquent "list index out of range" errors | https://github.com/open-webui/open-webui/discussions/3134 | consultée le 13/04/2026 |
| Auto-install dépendances | Le système installe automatiquement les packages listés dans `requirements:` du frontmatter via pip | https://github.com/open-webui/open-webui/discussions/3134 | consultée le 13/04/2026 |
| self.citation | `self.citation = True` dans `__init__` affiche le contexte de l'outil dans les réponses du frontend | https://github.com/open-webui/open-webui/discussions/3134 | consultée le 13/04/2026 |

### Contenu détaillé — Template minimal validé par la communauté :
```python
"""
title: Example Tool
author: Name
version: 1.0
requirements: package_name
"""

class Tools:
    def __init__(self):
        self.citation = True  # Affiche le contexte de l'outil dans les réponses
    
    def function_name(self, param: str) -> str:
        """
        Description of what function does.
        :param param: Parameter description.
        :return: Return value description.
        """
        # implementation
```

### Contenu détaillé — Exemples communautaires validés :

**Outil de recherche web (DuckDuckGo) :**
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

**Outil heure courante :**
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

**Outil requête SQL (avec Valves) :**
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

### Contenu détaillé — Problèmes fréquents documentés :

| Problème | Cause | Solution |
|----------|-------|----------|
| "Something went wrong :/ list index out of range" | Docstrings ou type hints manquants | Ajouter docstrings Sphinx-style complets et type hints |
| Tool jamais appelé par le modèle | Tool non activé pour le modèle | Activer dans workspace model settings |
| Tool absent de l'UI | Corruption du volume Docker | Reset du volume Docker (pas seulement le conteneur) |
| Tool appelé mais ne retourne rien | Modèle trop faible | Utiliser un modèle plus puissant (gpt-4o, Llama 3.1) |
| ImportError pour les packages | Dépendances non installées | Ajouter au frontmatter `requirements:` |

### Contenu détaillé — Modèles recommandés pour le function calling :

- gpt-4o (OpenAI)
- Llama 3.1-GROQ
- Gemini 1.5
- mistral-small:22b-instruct

Les modèles faibles (Llama 3 8B standard) échouent souvent à sélectionner le bon outil. Le modèle doit être entraîné sur des patterns de function-calling pour invoquer les outils de manière fiable.

### Contenu détaillé — Bonnes pratiques communautaires :

1. **Toujours inclure des docstrings** : "Without a docstring the calling LLM doesn't know what the function is for."
2. **Type hints obligatoires** sur tous les paramètres et retours
3. **Gestion d'erreurs** : wraper la logique dans try-except retournant des chaînes d'erreur significatives
4. **Tester localement** avant déploiement production
5. **Commencer simple** : tester avec des prompts directs ("Tell the LLM to use it")
6. **Consulter les logs** : `docker logs open-webui` pour les détails d'exécution
7. **Support async** : utiliser `async`/`await` pour les opérations réseau

**Source :** https://github.com/open-webui/open-webui/discussions/3134 — consultée le 13/04/2026

## 7.6 Issue #8292 : Bug __event_emitter__ pour les Action functions

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Bug | `__event_emitter__` échoue dans les Action functions avec exception `'user_id'` | https://github.com/open-webui/open-webui/issues/8292 | consultée le 13/04/2026 |
| Cause racine | L'implémentation de l'event emitter ne reçoit pas correctement le contexte utilisateur quand invoquée depuis les Actions | https://github.com/open-webui/open-webui/issues/8292 | consultée le 13/04/2026 |
| Résolution | FERMÉ comme COMPLÉTÉ — PR #8246 merged le 5 janvier 2025 | https://github.com/open-webui/open-webui/issues/8292 | consultée le 13/04/2026 |
| Finding additionnel | Les Actions doivent retourner `None` plutôt que `return body` — retourner le body cause la suppression non intentionnelle du message | https://github.com/open-webui/open-webui/issues/8292 | consultée le 13/04/2026 |

### Contenu détaillé — Code de reproduction :
L'Action tente 3 émissions séquentielles :
1. Status update : `"processing"` avec `done: False`
2. Message append : `"**message 1**"`
3. Status update : `"process done!"` avec `done: True`

Chaque event via `await __event_emitter__()` avec dictionnaires `{type, data}`.

**Note pour le corpus :** Ce bug (résolu) révèle que le système d'événements pour les Actions a eu des problèmes de contexte utilisateur. Toujours retourner `None` depuis une Action pour éviter des effets de bord (suppression de message).

---

# DONNÉES NON TROUVÉES (Lot 2)

| Donnée recherchée | Statut | Commentaire |
|--------------------|--------|-------------|
| Bibliothèque communautaire openwebui.com/functions | HTTP 403 | Toutes les pages individuelles aussi inaccessibles. Contournement via GitHub repos tiers. |
| Code source complet des exemples communautaires sur openwebui.com | Inaccessible | Pages f/hub/custom_action, f/hub/autotool_filter, f/podden/anthropic_pipe toutes en 403 |
| Contenu des sous-dossiers pipelines/examples/pipelines/integrations/ providers/ rag/ | Non exploré en détail | Seule la structure de premier niveau a été collectée |
| Dates de dernière modification des fichiers du dépôt docs | Non disponibles | L'interface directory listing de GitHub ne les affiche pas — nécessiterait git log |
| Sections en brouillon ou non déployées dans le dépôt docs | Non trouvées | La doc live semble à jour par rapport aux sources MDX |

---

*Fin du Lot 2 — Sources 5 à 7*
*Prêt pour le Lot 3 (Sources 8 à 11) sur validation*