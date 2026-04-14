# Plan : Restructuration documentation Open WebUI

## Statut : VALIDÉ — En attente d'exécution

## Objectif
Transformer les 4 fichiers source (plan.md, lot1-3.md) en 16 fichiers MD thématiques, orientés développeur, avec zéro perte d'information.

## Fichiers source à supprimer après écriture
- `docs/plan.md`
- `docs/lot1.md`
- `docs/lot2.md`
- `docs/lot3.md`

## Fichiers à créer (16)

### 01-introduction.md
- Périmètre, public cible, version v0.8.12
- Conventions de notation
- Sources consultées (tableau avec URL + fiabilité)
- Structure du corpus (table des matières vers les 15 autres fichiers)
- **Source :** plan §1 + lot1 en-tête

### 02-extension-taxonomy.md
- Taxonomie complète : Tools, Pipe, Filter, Action, Pipelines
- 3 couches d'extensibilité (In-process Python, External HTTP, Pipeline workers)
- Tableau comparatif (quoi, qui appelle, où ça tourne, UI)
- Distinction Functions internes vs Pipelines externes
- Confusion nomenclature connue (Discussion #16415)
- Distinction OpenAPI vs MCP vs Tools Python natifs
- **Source :** lot1 §1.1-1.2, lot2 §6.1, lot3 §8.3

### 03-architecture-lifecycle.md
- Cycle de vie Function : stockage BDD → chargement → injection params → exécution → streaming
- Cycle de vie Tool : stockage → chargement → contrôle accès → injection invisible → exécution
- Mécanisme `exec` et injection de dépendances via `inspect.signature()`
- Schéma BDD : tables `function` et `tool` avec colonnes détaillées
- Modèles Pydantic associés (FunctionModel, ToolModel, etc.)
- Méthodes CRUD principales
- Pipeline scaffolds : `on_startup`, `on_shutdown`, `on_valves_updated`, manifold pattern
- Types de Tools : Builtin, Local, OpenAPI, Terminal
- Contrôle d'accès : 3 niveaux (bypass admin, creator-only, group-based grants)
- Flux de données complet : User Input → Inlet Filters → RAG Query → LLM Call → Outlet Filters → UI Display
- **Source :** lot1 §2, §10, lot2 §6.1, scaffolds GitHub

### 04-reserved-parameters.md
- Tableau complet : paramètre, type, disponibilité, description
- Détails `__metadata__` : structure complète avec variables (USER_NAME, CURRENT_DATETIME, etc.), features, interface
- Détails `__model__` : structure complète avec info, params, meta, capabilities, access_control
- Détails `__files__` : structure complète avec accès fichier physique
- Détails `__user__` : id, email, name, role, valves
- `__tools__`, `__task__`, `__task_body__`, `__oauth_token__`, `__id__`
- Détection source requête : `__metadata__["interface"]`
- Accès fichier physique : `Path(f"/app/backend/data/uploads/{id}_{filename}")`
- **Source :** lot1 §3

### 05-valves.md
- Définition Valves (pydantic.BaseModel, champs GUI)
- Valves vs UserValves (admin vs utilisateur)
- Persistance : Valves system-wide, UserValves par utilisateur
- Accès : `self.valves.field_name` vs `__user__["valves"].field_name`
- ATTENTION : `__user__["valves"]["field_name"]` retourne la valeur par défaut, pas la valeur réelle !
- Types de champs : int, bool, string avec Literal, password, select statique, select dynamique
- Champ requis avec `required=True`
- Champ priority : `priority: int = Field(default=0)` — valeurs basses exécutées en premier
- **Source :** lot1 §4

### 06-event-system.md
- `__event_emitter__` : one-way backend → frontend
- `__event_call__` : bidirectionnelle, timeout 300s (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`)
- Tableau complet des types d'événements avec helper, data structure, persistance BDD
- Exemples code : status, confirmation, input, input password, execute JS, formulaire custom, citation
- Persistance : noms courts (message, replace, files, status, source) → BDD ; noms longs → Socket.IO only
- Événements requérant connexion live : confirmation, input, execute via `__event_call__`
- Matrice de compatibilité par type de fonction (Tools/Actions/Pipes/Filters)
- Événements pour outils externes : headers X-Open-WebUI-Chat-Id/Message-Id, endpoint REST
- Citations : `self.citation = False` pour désactiver auto-citations, structure metadata avec types
- **Source :** lot1 §5, Context7 (citations détaillées)

### 07-tools.md
- Structure de base complète avec frontmatter (title, author, requirements, etc.)
- Exigences critiques : type hints obligatoires, docstrings, async recommandé
- Types primitifs uniquement : `str`, `int`, `float`, `bool` (Discussion #13174)
- Gestion packages externes via frontmatter `requirements:`
- ATTENTION production : `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False` + pré-installer via Dockerfile
- Race conditions multi-worker avec pip install runtime
- Modes de Tool Calling : Default (Legacy) vs Native (Agentic)
- Incompatibilité Native Mode : message/replace/chat:message:delta cassés
- Pattern de détection du mode via `__metadata__`
- `self.citation = True` pour afficher le contexte
- Built-in System Tools (Native Mode) : search, code, memory, knowledge, notes, chat history, code interpreter, image generation, channels, time
- Contrôle d'accès des tools attachés
- Exemples : String Inverse, DuckDuckGo Search, SQL Query, heure courante
- Modèles recommandés pour function calling
- **Source :** lot1 §6.1+§11, lot2 §7.5, lot3 §9, Context7

### 08-pipes.md
- Structure de base Pipe avec Valves
- Méthode `pipes()` : liste de modèles sélectionnables
- Manifold Pattern : `self.type = "manifold"`, `self.pipelines` list, IDs composites
- Paramètres de `pipe()` : body, __user__, __request__ (obligatoire depuis 0.5.0)
- Streaming : `r.iter_lines()` vs `r.json()`
- Accès fonctions internes : `from open_webui.utils.chat import generate_chat_completion`
- `Users.get_user_by_id()` (await en 0.9.0+)
- Pipeline scaffold : `on_startup`, `on_shutdown`, `on_valves_updated`
- **Source :** lot1 §6.2, GitHub scaffolds

### 09-filters.md
- Structure de base Filter avec Valves, toggle, icon
- `inlet()` : pré-traitement, toujours appelé (WebUI + API), clés réservées
- `stream()` : interception temps réel, structure event chunks
- `outlet()` : post-traitement, NON appelé pour API directes, `POST /api/chat/completed`
- Comportement API : inlet ✅, stream ✅, outlet ❌ (API directe)
- Système global/spécifique : is_active × is_global
- Toggleable vs Always-On
- **Source :** lot1 §6.3

### 10-actions.md
- Structure de base Action
- Multi-Actions avec `__id__` et liste actions
- Ordre boutons : priority ascending, puis alphabétique par function ID
- Frontmatter : title, author, version, required_open_webui_version, icon_url
- icon_url DOIT utiliser des URLs hébergées, jamais base64
- Valeur de retour : `{"content": "...", "files": [...]}`
- CRITIQUE : Toujours retourner `None` pour éviter suppression message (Issue #8292)
- `async` obligatoire
- **Source :** lot1 §6.4, lot3 §8.1

### 11-rich-ui.md
- Mécanisme `HTMLResponse` avec header `Content-Disposition: inline`
- Disponibilité : Tools ✅, Actions ✅, Pipes ❌, Filters ❌
- Position rendu : Tools inline, Actions au-dessus du message
- Fournir du contexte au LLM via tuple (HTMLResponse, result_context)
- Gestion hauteur iframe via postMessage
- Sandbox flags : allow-scripts, allow-popups, allow-downloads (toujours actifs)
- Sandbox configurables : allowSameOrigin, allowForms
- allowSameOrigin OFF (défaut) : isolation complète, postMessage requis
- allowSameOrigin ON : accès parent, auto-resize, Chart.js/Alpine.js auto-injectés
- Communication avancée : `window.args` (Tools seulement), prompt submission (input:prompt, input:prompt:submit, action:submit)
- Rich UI vs Execute Event : tableau comparatif
- **Source :** lot1 §7

### 12-external-tools.md
- **OpenAPI Tool Servers** : pourquoi OpenAPI, quickstart, limitations (one-way events, pas streaming)
- CORS requis pour serveurs locaux, HTTPS requis en production
- N'importe quel framework/langage si OpenAPI spec valide
- operationId custom requis pour tous les endpoints
- `TOOL_SERVER_CONNECTIONS` env var : JSON array de configurations
- **MCP natif** (v0.6.31+) : Streamable HTTP uniquement, pas stdio/SSE natif
- Configuration : Admin Settings → External Tools → Type MCP
- Auth modes : None, Bearer, OAuth 2.1, OAuth 2.1 (Static)
- `WEBUI_SECRET_KEY` obligatoire pour OAuth (sinon tokens cassés au restart)
- OAuth 2.1 tools ne peuvent pas être default/pre-enabled sur un modèle
- Fonction Name Filter List workaround (virgule seule)
- **MCPO Proxy** : bridge stdio/SSE MCP → OpenAPI HTTP
- Quickstart : `uvx mcpo --port 8000 -- uvx mcp-server-time`
- Dockerfile example pour déploiement
- MCP vs OpenAPI : quand choisir quoi
- FAQ OpenAPI : CORS, frameworks, sécurité, multi-servers, testing
- **Source :** Context7, GitHub docs (mcp.mdx, openapi-servers/)

### 13-security.md
- Exécution arbitraire : "Workspace Tools execute arbitrary Python code"
- Équivalence shell : "Granting ability to create Tools = giving shell access"
- Restriction création aux administrateurs
- Répertoire données : `/app/backend/data` dans Docker
- Execute JS non sandboxé : accès complet DOM/cookies/localStorage
- Risques Pipelines : accès filesystem, exfiltration, mining
- Fuite données via `functools.partial` (Issue #16307) : clés API, passwords visibles
- Recommandations : filtrer manuellement données sensibles, ne jamais exposer __user__ aux LLMs externes
- Typage __event_emitter__ : Callable, jamais None
- **Source :** lot1 §9, lot3 §8.2

### 14-development-debugging.md
- 3 méthodes de déploiement : éditeur code direct, marketplace, fichiers JSON
- Configuration Docker pour persistance (bind mount /app/data)
- Pré-chargement Tools/Functions avant premier démarrage (Discussion #8955)
- Endpoint API non documenté : `POST /api/v1/functions/create`
- Problème montage config.json : `OSError: [Errno 16]` via os.rename
- Erreurs fréquentes et solutions (tableau : list index out of range, tool jamais appelé, ImportError, etc.)
- Débogage : `docker logs open-webui`
- Bonnes pratiques communautaires (7 points)
- Modèles recommandés pour function calling
- Tool skeleton template : EventEmitter helper (progress_update, error_update, success_update)
- **Source :** lot2 §7.5+§10.2, lot3 §7.6+§8.2-8.3

### 15-migrations.md
- Migration 0.4 → 0.5.0 : sub-app → single FastAPI, import paths, `__request__` obligatoire, API generate_chat_completion
- Migration → 0.9.0 : data layer async bout en bout, coroutines, SQLAlchemy 2.0 async, patterns requête (.first()→.scalars().first(), .all()→.scalars().all(), .count()→.scalar_one())
- anyio.to_thread.run_sync pour dépendances sync
- Avant/Après code pour chaque migration
- **Source :** lot1 §8

### 16-known-issues-resources.md
- Bugs résolus (historique) : event_emitter outlet, event_emitter Actions, caractères corrompus status, contenu outlet non persisté
- Limitations actuelles non résolues : type hints limités, fuite partial, native calling peu fiable, citations fusionnées, events indisponibles pour externes, duplication system prompt, outlet non appelé API, message events cassés Native
- Feature requests révélant les limites
- Dépôts communautaires : owndev/Open-WebUI-Functions (Azure, N8N, Gemini), Haervwe/open-webui-tools (20+ outils), open-webui/pipelines examples
- Exemples officiels : 16 filtres, 4 scaffolds
- Bibliothèque communautaire : 541 fonctions, 276 outils (inaccessible 403 au moment collecte)
- Patterns architecturaux observés
- **Source :** lot2 §7, lot3 §8 (synthèse)

## Garantie zéro perte

Chaque donnée factuelle des 3 lots + plan est mappée à un fichier cible dans le tableau ci-dessus. Aucune information n'est omise — la restructuration est une redistribution, pas un résumé.

## Informations ajoutées (vérifiées via Context7 + GitHub)

| Sujet | Source vérification |
|-------|-------------------|
| MCP natif v0.6.31+ | Context7 (/open-webui/docs) + GitHub mcp.mdx |
| OpenAPI Tool Servers | GitHub docs openapi-servers/index.mdx + faq.mdx |
| MCPO Proxy | GitHub docs openapi-servers/mcp.mdx |
| Pipeline scaffolds code | GitHub open-webui/pipelines/examples/scaffolds/ |
| Citations détaillées | Context7 (/open-webui/docs) |
| ENABLE_PIP_INSTALL prod | Context7 (/open-webui/docs) |
| TOOL_SERVER_CONNECTIONS env var | Context7 (/open-webui/docs) |
