# Corpus documentaire — Open WebUI : Création d'outils custom
## LOT 1 : Sources 1 à 4 (Documentation officielle + Code source)

**Version cible :** Open WebUI v0.8.12 (publiée le 27 mars 2025)
**Date de collecte :** 13 avril 2026

---

# CATÉGORIE 1 : ARCHITECTURE GÉNÉRALE DU SYSTÈME D'EXTENSIBILITÉ

## 1.1 Taxonomie des types d'extensions

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Types d'extensions principaux | Tools, Functions (Pipe, Filter, Action), Pipelines | https://docs.openwebui.com/features/extensibility/plugin/ | consultée le 13/04/2026 |
| Trois couches d'extensibilité | 1) In-process Python (Tools & Functions) — s'exécute dans Open WebUI ; 2) External HTTP (OpenAPI & MCP servers) — services externes ; 3) Pipeline workers (Pipelines) — conteneur séparé | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |
| Définition Tool | Scripts Python exécutés dans l'environnement Open WebUI, appelés par le LLM via function calling | https://docs.openwebui.com/features/extensibility/plugin/tools/development/ | consultée le 13/04/2026 |
| Définition Pipe Function | Se présente comme un modèle autonome dans l'interface, traite les requêtes avec logique custom | https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ | consultée le 13/04/2026 |
| Définition Filter Function | Modifie les données en entrée (inlet), en streaming (stream) et en sortie (outlet) du LLM | https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ | consultée le 13/04/2026 |
| Définition Action Function | Boutons interactifs dans la barre de messages, exécute du Python côté serveur | https://docs.openwebui.com/features/extensibility/plugin/functions/action/ | consultée le 13/04/2026 |
| Définition Pipeline | Service séparé, UI-Agnostic OpenAI API Plugin Framework, pour tâches lourdes | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |

### Contenu détaillé :

**Tools** : "Python scripts that run directly within the Open WebUI environment" avec les capacités complètes de Python. Appelés par le LLM via deux modes de function calling (Default et Native). Les Tools sont gérés dans les onglets Workspace. Sécurité : "Workspace Tools execute arbitrary Python code on your server. Only install from trusted sources, review code before importing, and restrict Workspace access to trusted administrators only. Granting a user the ability to create or import Tools is equivalent to giving them shell access."

**Functions** : Trois sous-types (Pipe, Filter, Action) gérés depuis l'Admin Panel. Les Functions aident "the WebUI itself do more things, like adding new AI models". Exécution via `exec` dans le processus Open WebUI.

**Pipelines** : Service séparé déployé via Docker (`ghcr.io/open-webui/pipelines:main`), port 9099. Recommandé quand "dealing with computationally heavy tasks that you want to offload from your main Open WebUI instance for better performance and scalability." Compatible avec tout client supportant l'API OpenAI.

## 1.2 Différence Functions internes vs Pipelines externes

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Functions internes | S'exécutent dans le processus Open WebUI, pas d'import de packages supplémentaires natif (sauf via frontmatter requirements) | https://docs.openwebui.com/features/extensibility/plugin/ | consultée le 13/04/2026 |
| Pipelines externes | Service séparé, conteneur Docker dédié, Python 3.11 requis, peut importer n'importe quel package | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |
| Quand utiliser Pipelines | "If your goal is simply to add support for additional providers...you likely don't need Pipelines." Utiliser les Functions internes pour les cas basiques. | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |
| Docker Pipelines | `docker run -d -p 9099:9099 --add-host=host.docker.internal:host-gateway -v pipelines:/app/pipelines --name pipelines --restart always ghcr.io/open-webui/pipelines:main` | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |
| Connexion | Admin Panel > Settings > Connections, URL: `http://localhost:9099`, API key: `0p3n-w3bu!` | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |
| Chargement automatique | Tous les pipelines dans `/pipelines` sont chargés au démarrage. Configurable via `PIPELINES_DIR` | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |

## 1.3 Modes de Tool Calling

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Default Mode (Legacy) | Injection dans le prompt, compatibilité universelle, "breaks KV cache" entre les tours, ne supporte pas les system tools | https://docs.openwebui.com/features/extensibility/plugin/tools/ | consultée le 13/04/2026 |
| Native Mode (Agentic) | Utilise la capacité native de function-calling du modèle, définitions structurées, multi-step, requiert modèles frontier (GPT-5, Claude 4.5 Sonnet, Gemini 3 Flash, MiniMax M2.5) | https://docs.openwebui.com/features/extensibility/plugin/tools/ | consultée le 13/04/2026 |
| Incompatibilité Native Mode | "Message events (message, chat:message, chat:message:delta, replace) are BROKEN in Native mode because the server emits repeated content snapshots that overwrite tool-emitted updates." | https://docs.openwebui.com/features/extensibility/plugin/tools/development/ | consultée le 13/04/2026 |

---

# CATÉGORIE 2 : CYCLE DE VIE ET MÉCANISME D'EXÉCUTION

## 2.1 Cycle de vie d'une fonction custom

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Stockage | Table `function` en base de données avec colonnes : id, user_id, name, type, content, meta (JSON), valves (JSON), is_active, is_global, updated_at, created_at | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/functions.py | consultée le 13/04/2026 |
| Chargement | `get_function_module_by_id(request, pipe_id)` — récupère le module avec cache, initialise les Valves depuis la BDD | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |
| Énumération des modèles Pipe | `get_function_models(request)` — énumère toutes les fonctions pipe actives, gère les manifolds (pipes multiples), génère des IDs composites `pipe.id.sub_id` | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |
| Exécution principale | `generate_function_chat_completion(request, form_data, user, models)` — extrait metadata, construit `extra_params` avec les paramètres injectés, charge le module, exécute le pipe | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |
| Injection de paramètres | `get_function_params(function_module, form_data, user, extra_params)` — utilise `inspect.signature()` pour matcher extra_params avec les paramètres déclarés par la fonction | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |
| Exécution pipe | `execute_pipe(pipe, params)` — détecte si la fonction est async ou sync, exécute avec les paramètres injectés | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |
| Réponse streaming | Si `form_data['stream']` est True, réponses wrappées dans `StreamingResponse` au format event-stream. Supporte : string, Generator sync, AsyncGenerator | https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py | consultée le 13/04/2026 |

## 2.2 Cycle de vie d'un Tool

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Stockage Tool | Table `tool` : id, user_id, name, content, specs (JSON), meta (JSON), valves (JSON), updated_at, created_at | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/tools.py | consultée le 13/04/2026 |
| Chargement Tools | `get_tools()` dans utils/tools.py — vérifie le contrôle d'accès, charge les modules, applique les Valves, injecte les paramètres, gère les collisions de noms | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py | consultée le 13/04/2026 |
| Types de Tools | Builtin (hardcoded: search, code, memory), Local (BDD + plugin loader), OpenAPI (serveurs externes), Terminal (CLI) | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py | consultée le 13/04/2026 |
| Injection invisible | `get_async_tool_function_and_apply_extra_params()` — wrappe les fonctions pour injecter __id__, __user__, etc. tout en les masquant de la signature visible par le modèle | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py | consultée le 13/04/2026 |
| Contrôle d'accès | 3 niveaux : bypass admin, propriétaire du tool (creator-only), grants d'accès (group-based) | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py | consultée le 13/04/2026 |

---

# CATÉGORIE 3 : PARAMÈTRES INJECTÉS (API IMPLICITE)

## 3.1 Référence complète des paramètres réservés

| Paramètre | Type | Toujours disponible | Description | URL source | Date source |
|-----------|------|---------------------|-------------|------------|-------------|
| `body` | dict | Oui | Dictionnaire de la requête de chat completion : stream, model, messages, features, stream_options, metadata, files | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__user__` | dict | Oui | `{id, email, name, role ("user"\|"admin"), valves (si UserValves défini)}` | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__metadata__` | dict | Oui | `{user_id, chat_id, message_id, session_id, tool_ids, tool_servers, files, features, variables, model, direct, function_calling, type, interface}` | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__model__` | dict | Oui | Objet modèle complet : id, name, object, created, owned_by, info (base_model_id, params, meta, access_control, is_active), preset, actions, tags | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__messages__` | list | Oui | Liste des messages, identique à `body["messages"]` | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__chat_id__` | str | Contexte chat | UUID unique de la conversation | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__session_id__` | str | Généralement | Identifiant de session | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__message_id__` | str | Contexte chat | Identifiant du message courant | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__event_emitter__` | Callable | Contexte fonction | Communication one-way vers le frontend | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__event_call__` | Callable | Contexte action | Communication bidirectionnelle, timeout 300s (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`) | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__files__` | list | Oui ([] si vide) | Liste d'objets fichiers (images exclues — envoyées en base64 dans messages). Structure : type, file (id, filename, user_id, hash, data, meta), url, status | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__request__` | fastapi.Request | Oui | Instance Request FastAPI | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__task__` | str | Contexte tâche | Type de tâche interne : title_generation, tags_generation, emoji_generation, query_generation, image_prompt_generation, autocomplete_generation, function_calling, moa_response_generation | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__task_body__` | dict | Contexte tâche | Body spécifique à la tâche interne | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__tools__` | list | Oui | Liste d'instances ToolUserModel | https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args | consultée le 13/04/2026 |
| `__id__` | str | Actions | Identifiant de l'action (utile pour multi-actions) | https://docs.openwebui.com/features/extensibility/plugin/functions/action/ | consultée le 13/04/2026 |
| `__oauth_token__` | dict | Si configuré | Token OAuth de l'utilisateur (auto-refreshed) | https://docs.openwebui.com/features/extensibility/plugin/tools/development/ | consultée le 13/04/2026 |

### Contenu détaillé — Structure de `__metadata__` :
```python
{
  "user_id": "uuid",
  "chat_id": "uuid",
  "message_id": "uuid",
  "session_id": "string",
  "tool_ids": null|[list of str],
  "tool_servers": [],
  "files": "[Same as __files__]",
  "features": {
    "image_generation": false,
    "code_interpreter": false,
    "web_search": false
  },
  "variables": {
    "{{USER_NAME}}": "cheesy_username",
    "{{USER_LOCATION}}": "Unknown",
    "{{CURRENT_DATETIME}}": "2025-02-02 XX:XX:XX",
    "{{CURRENT_DATE}}": "2025-02-02",
    "{{CURRENT_TIME}}": "XX:XX:XX",
    "{{CURRENT_WEEKDAY}}": "Monday",
    "{{CURRENT_TIMEZONE}}": "Europe/Berlin",
    "{{USER_LANGUAGE}}": "en-US"
  },
  "model": "[Identical to __model__]",
  "direct": false,
  "function_calling": "native",
  "type": "user_response",
  "interface": "open-webui|other"
}
```

### Contenu détaillé — Structure de `__model__` :
```python
{
  "id": "my-cool-model",
  "name": "Display Name",
  "object": "model",
  "created": 1746000000,
  "owned_by": "openai|ollama",
  "info": {
    "id": "my-cool-model",
    "user_id": "uuid",
    "base_model_id": "gpt-4o",
    "name": "My Cool Model",
    "params": {
      "system": "System prompt...",
      "function_calling": "native"
    },
    "meta": {
      "profile_image_url": "/static/favicon.png",
      "description": "Model description",
      "capabilities": {"vision": true, "usage": true, "citations": true},
      "position": 17,
      "tags": [{"name": "tag_name"}],
      "suggestion_prompts": null
    },
    "access_control": {
      "read": {"group_ids": [], "user_ids": []},
      "write": {"group_ids": [], "user_ids": []}
    },
    "is_active": true,
    "updated_at": 1740000000,
    "created_at": 1740000000
  },
  "preset": true,
  "actions": [],
  "tags": [{"name": "tag_name"}]
}
```

### Contenu détaillé — Structure de `__files__` :
```python
[{
  "type": "file",
  "file": {
    "id": "uuid",
    "filename": "document.pdf",
    "user_id": "uuid",
    "hash": "hex_string",
    "data": {"content": "Parsed document content..."},
    "meta": {
      "name": "document.pdf",
      "content_type": "application/pdf",
      "size": 10486578,
      "data": {},
      "collection_name": "file-96xxxxxx..."
    },
    "created_at": 1740000000,
    "updated_at": 1740000000
  },
  "id": "uuid",
  "url": "/api/v1/files/uuid",
  "name": "document.pdf",
  "collection_name": "file-96xxxxxx...",
  "status": "uploaded",
  "size": 10486578,
  "error": "",
  "itemId": "uuid"
}]
```

**Accès au fichier physique :**
```python
from pathlib import Path
the_file = Path(f"/app/backend/data/uploads/{__files__[0]['file']['id']}_{__files__[0]['file']['filename']}")
assert the_file.exists()
```

### Détection de la source de la requête :
```python
if __metadata__ and __metadata__.get("interface") == "open-webui":
    # Requête depuis l'interface web
else:
    # Requête API directe
```

---

# CATÉGORIE 4 : SYSTÈME DE VALVES

## 4.1 Spécification complète des Valves

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Définition Valves | Configuration dynamique via champs GUI, héritent de `pydantic.BaseModel` | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |
| Valves vs UserValves | Valves : configurables par admins uniquement (Tools/Functions menus). UserValves : configurables par tout utilisateur depuis une session de chat | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |
| Persistance Valves | Persistées system-wide, accessibles à toutes les exécutions du plugin | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |
| Persistance UserValves | Par utilisateur, stockées dans `user.settings.functions.valves[function_id]` | https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/functions.py | consultée le 13/04/2026 |
| Accès Valves | `self.valves.field_name` | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |
| Accès UserValves | `__user__["valves"].field_name` — ATTENTION : `__user__["valves"]["field_name"]` retourne la valeur par défaut, pas la valeur réelle ! | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |
| Champ priority | `priority: int = Field(default=0)` — valeurs basses exécutées en premier | https://docs.openwebui.com/features/extensibility/plugin/development/valves | consultée le 13/04/2026 |

### Contenu détaillé — Types de champs :

**Types de base :**
```python
# Integer
test_valve: int = Field(default=4, description="...")

# Boolean (rendu comme switch)
test_user_valve: bool = Field(default=False, description="...")

# String avec choix
choice_option: Literal["choiceA", "choiceB"] = Field(default="choiceA", description="...")
```

**Champ mot de passe (masqué) :**
```python
service_password: str = Field(
    default="",
    description="Your service password",
    json_schema_extra={"input": {"type": "password"}}
)
```

**Dropdown select statique :**
```python
log_level: str = Field(
    default="info",
    description="Logging verbosity",
    json_schema_extra={
        "input": {
            "type": "select",
            "options": [
                {"value": "debug", "label": "Debug (Verbose)"},
                {"value": "info", "label": "Info (Standard)"},
                {"value": "warn", "label": "Warning (Minimal)"},
                {"value": "error", "label": "Error (Critical Only)"}
            ]
        }
    }
)
```

**Dropdown select dynamique :**
```python
selected_model: str = Field(
    default="",
    description="Choose a model to use",
    json_schema_extra={
        "input": {
            "type": "select",
            "options": "get_model_options"  # Nom de méthode comme string
        }
    }
)

@classmethod
def get_model_options(cls, __user__=None) -> list[dict]:
    return [
        {"value": "gpt-4", "label": "GPT-4"},
        {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"}
    ]
```

**Champ requis :**
```python
api_key: str = Field(default="", description="API key", required=True)
```

---

# CATÉGORIE 5 : SYSTÈME D'ÉVÉNEMENTS

## 5.1 Event Emitter (`__event_emitter__`)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Nature | Communication one-way backend → frontend | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Syntaxe | `await __event_emitter__({"type": "event_type", "data": {...}})` | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Disponibilité | Tools ✅, Actions ✅, Pipes ✅, Filters ✅ | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |

## 5.2 Event Call (`__event_call__`)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Nature | Communication bidirectionnelle, attend la réponse utilisateur | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Timeout par défaut | 300 secondes, configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT` | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Disponibilité | Tools ✅, Actions ✅, Pipes ✅, Filters ✅ | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |

## 5.3 Référence complète des types d'événements

| Type | Helper | Data Structure | Persisté en BDD | URL source |
|------|--------|----------------|------------------|------------|
| `status` | `__event_emitter__` | `{description: str, done: bool, hidden: bool}` | Oui (statusHistory) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:message:delta` / `message` | `__event_emitter__` | `{content: str}` | `message` oui (content), `chat:message:delta` non | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:message` / `replace` | `__event_emitter__` | `{content: str}` | `replace` oui (content), `chat:message` non | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `files` / `chat:message:files` | `__event_emitter__` | `{files: [...]}` | `files` oui | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:title` | `__event_emitter__` | `{title: str}` | Non (Socket.IO only) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:tags` | `__event_emitter__` | `{tags: [...]}` | Non (Socket.IO only) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `source` / `citation` | `__event_emitter__` | Open WebUI Source/Citation Object | Oui (sources) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `notification` | `__event_emitter__` | `{type: "info"\|"success"\|"warning"\|"error", content: str}` | Non (Socket.IO only) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `confirmation` | `__event_call__` | `{title: str, message: str}` | N/A (requiert connexion live) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `input` | `__event_call__` | `{title: str, message: str, placeholder: str, value: any, type: "password"\|optional}` | N/A (requiert connexion live) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `execute` | Les deux | `{code: "...javascript..."}` | Non | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:message:favorite` | `__event_emitter__` | `{favorite: bool}` | Non (Socket.IO only) | https://docs.openwebui.com/features/extensibility/plugin/development/events |
| `chat:completion` | `__event_emitter__` | Custom | Non (Socket.IO only) | https://docs.openwebui.com/features/extensibility/plugin/development/events |

### Contenu détaillé — Exemples de code complets :

**Status Event :**
```python
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Step 1/3: Fetching data...",
        "done": False,
        "hidden": False,
    },
})
# IMPORTANT : Toujours émettre un status final avec done: True pour arrêter l'animation shimmer
```

**Confirmation (bidirectionnelle) :**
```python
result = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Are you sure?",
        "message": "Do you really want to proceed?"
    }
})
if result:
    # Utilisateur a confirmé
else:
    # Utilisateur a annulé
```

**Input (bidirectionnel) :**
```python
result = await __event_call__({
    "type": "input",
    "data": {
        "title": "Enter your name",
        "message": "We need your name to proceed.",
        "placeholder": "Your full name"
    }
})
user_input = result
```

**Input password :**
```python
result = await __event_call__({
    "type": "input",
    "data": {
        "title": "Enter API Key",
        "message": "Your API key is required.",
        "placeholder": "sk-...",
        "type": "password"
    }
})
```

**Execute JavaScript (bidirectionnel avec retour) :**
```python
result = await __event_call__({
    "type": "execute",
    "data": {
        "code": "return document.title;",
    }
})
```

**Execute JavaScript (fire-and-forget) :**
```python
await __event_emitter__({
    "type": "execute",
    "data": {
        "code": """
            (function() {
                const blob = new Blob([data], {type: 'application/octet-stream'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'file.bin';
                document.body.appendChild(a);
                a.click();
                URL.revokeObjectURL(url);
                a.remove();
            })();
        """
    }
})
```

**Formulaire custom via execute :**
```python
result = await __event_call__({
    "type": "execute",
    "data": {
        "code": """
            return new Promise((resolve) => {
                const overlay = document.createElement('div');
                overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999';
                overlay.innerHTML = `
                    <div style="background:white;padding:24px;border-radius:12px;min-width:300px">
                        <h3 style="margin:0 0 12px">Enter Details</h3>
                        <input id="exec-name" placeholder="Name" style="width:100%;padding:8px;margin:4px 0;border:1px solid #ccc;border-radius:6px"/>
                        <input id="exec-email" placeholder="Email" style="width:100%;padding:8px;margin:4px 0;border:1px solid #ccc;border-radius:6px"/>
                        <button id="exec-submit" style="margin-top:12px;padding:8px 16px;background:#333;color:white;border:none;border-radius:6px;cursor:pointer">Submit</button>
                    </div>
                `;
                document.body.appendChild(overlay);
                document.getElementById('exec-submit').onclick = () => {
                    const name = document.getElementById('exec-name').value;
                    const email = document.getElementById('exec-email').value;
                    overlay.remove();
                    resolve({ name, email });
                };
            });
        """
    }
})
# result = {"name": "...", "email": "..."}
```

**Citation :**
```python
class Tools:
    def __init__(self):
        self.citation = False  # REQUIS pour utiliser des citations custom
    
    async def research_tool(self, __event_emitter__=None) -> str:
        await __event_emitter__({
            "type": "citation",
            "data": {
                "document": ["Content text"],
                "metadata": [{
                    "date_accessed": datetime.now().isoformat(),
                    "source": "Title",
                    "author": "Name",
                    "publication_date": "2024-01-01",
                    "url": "https://example.com"
                }],
                "source": {"name": "Title", "url": "https://example.com"}
            }
        })
```

## 5.4 Événements pour outils externes

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Prérequis | Variable d'environnement `ENABLE_FORWARD_USER_INFO_HEADERS=True` | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Headers fournis | `X-Open-WebUI-Chat-Id`, `X-Open-WebUI-Message-Id` (noms configurables) | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Endpoint | `POST /api/v1/chats/{chat_id}/messages/{message_id}/event` avec auth API key/session token | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |

## 5.5 Persistance des événements

| Catégorie | Événements | Comportement |
|-----------|-----------|-------------|
| Persistés en BDD | `status` → statusHistory, `message` → content, `replace` → content (écrase), `embeds` → embeds, `files` → files, `source`/`citation` → sources | Survivent à la déconnexion |
| Non persistés | `chat:completion`, `chat:message:delta`, `chat:message:error`, `chat:message:follow_ups`, `chat:message:favorite`, `chat:title`, `chat:tags`, `notification` | Socket.IO uniquement, perdus à la déconnexion |
| Requièrent connexion live | `confirmation`, `input`, `execute` via `__event_call__` | Erreur si déconnecté, timeout 300s |

**Source :** https://docs.openwebui.com/features/extensibility/plugin/development/events — consultée le 13/04/2026

**Note importante :** Utiliser les noms courts (`message`, `replace`, `files`, `status`, `source`) pour la persistance en BDD. Les noms longs (`chat:message:delta`, `chat:message:files`) fonctionnent côté frontend mais ne persistent pas.

## 5.6 Matrice de compatibilité par type de fonction

| Capacité | Tools | Actions | Pipes | Filters |
|----------|-------|---------|-------|---------|
| `__event_emitter__` | ✅ | ✅ | ✅ | ✅ |
| `__event_call__` | ✅ | ✅ | ✅ | ✅ |
| Return value → réponse utilisateur | ✅ | ✅ | ✅ | ❌ |
| `HTMLResponse` → Rich UI embed | ✅ | ✅ | ❌ | ❌ |

**Source :** https://docs.openwebui.com/features/extensibility/plugin/development/events — consultée le 13/04/2026

---

# CATÉGORIE 6 : SPÉCIFICATION PAR TYPE DE FONCTION

## 6.1 Tool (outil appelé par le LLM)

### Structure de base :
```python
"""
title: String Inverse
author: Your Name
author_url: https://website.com
git_url: https://github.com/username/string-reverse.git
description: This tool calculates the inverse of a string
required_open_webui_version: 0.4.0
requirements: langchain-openai, langgraph, ollama
version: 0.4.0
licence: MIT
"""

from pydantic import BaseModel, Field

class Tools:
    def __init__(self):
        self.valves = self.Valves()
    
    class Valves(BaseModel):
        api_key: str = Field("", description="Your API key here")
    
    class UserValves(BaseModel):
        preference: str = Field("default", description="User preference")
    
    async def reverse_string(self, string: str) -> str:
        """
        Reverses the input string.
        :param string: The string to reverse
        """
        return string[::-1]
```

**Source :** https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consultée le 13/04/2026

**Exigences critiques :**
- Type hints obligatoires pour chaque argument (utilisés pour la génération du JSON schema)
- Méthodes async recommandées pour compatibilité future
- Docstrings obligatoires décrivant les paramètres

**Gestion des packages externes (frontmatter) :**
```python
"""
requirements: langchain-openai>=0.1.0,requests,beautifulsoup4
"""
```
- ATTENTION : "When multiple tools define different versions of the same package... Open WebUI installs them in a non-deterministic order."
- Production : Set `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False` et pré-installer via Docker

### Compatibilité événements par mode :

| Type d'événement | Default Mode | Native Mode | Statut |
|------------------|-------------|-------------|--------|
| status | ✅ Complet | ✅ Identique | Compatible |
| message | ✅ Complet | ❌ Cassé | Incompatible |
| citation | ✅ Complet | ✅ Identique | Compatible |
| notification | ✅ Complet | ✅ Identique | Compatible |
| files | ✅ Complet | ✅ Identique | Compatible |
| replace | ✅ Complet | ❌ Cassé | Incompatible |
| chat:message:delta | ✅ Complet | ❌ Cassé | Incompatible |

**Source :** https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consultée le 13/04/2026

### Pattern de détection du mode :
```python
async def adaptive_tool(self, __event_emitter__=None, __metadata__=None) -> str:
    mode = "default"
    if __metadata__:
        mode = __metadata__.get("params", {}).get("function_calling", "default")
    is_native = (mode == "native")
```

## 6.2 Pipe Function (modèle/agent custom)

### Structure de base :
```python
from pydantic import BaseModel, Field

class Pipe:
    class Valves(BaseModel):
        API_KEY: str = Field(default="", description="Authentication credential")
        NAME_PREFIX: str = Field(default="PREFIX/", description="Display prefix")
        BASE_URL: str = Field(default="https://api.example.com", description="Endpoint")
    
    def __init__(self):
        self.valves = self.Valves()
    
    def pipes(self) -> list:
        return [
            {"id": "model-1", "name": "Display Name 1"},
            {"id": "model-2", "name": "Display Name 2"}
        ]
    
    async def pipe(self, body: dict, __user__: dict, __request__: Request) -> Any:
        model_id = body.get("model", "")
        # Logique de traitement
        pass
```

**Source :** https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ — consultée le 13/04/2026

**Paramètres de `pipe()` :**
- `body: dict` — payload de la requête (model, stream, messages, etc.)
- `__user__: dict` (optionnel) — informations utilisateur
- `__request__: Request` (optionnel, **obligatoire depuis 0.5.0**) — objet Request FastAPI

**Méthode `pipes()` :**
- Retourne une liste de `{"id": "...", "name": "..."}` 
- Chaque entrée apparaît comme un modèle sélectionnable dans l'interface
- Le modèle sélectionné est routé via `body["model"]`

**Streaming :**
```python
if body.get("stream", False):
    return r.iter_lines()  # Iterator pour streaming
else:
    return r.json()  # Réponse complète
```

**Accès aux fonctions internes :**
```python
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

user_obj = Users.get_user_by_id(__user__["id"])  # await en 0.9.0+
result = await generate_chat_completion(__request__, body, user_obj)
```

## 6.3 Filter Function (pré/post-traitement)

### Structure de base :
```python
from pydantic import BaseModel
from typing import Optional

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Lower values execute first")
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True  # Crée un switch dans l'UI
        self.icon = "https://example.com/icon.svg"
    
    async def inlet(self, body: dict, __event_emitter__=None, __user__=None, __metadata__=None, __model__=None) -> dict:
        return body
    
    def stream(self, event: dict) -> dict:
        return event
    
    def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
        pass
```

**Source :** https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ — consultée le 13/04/2026

### Méthodes détaillées :

**`inlet()` — Pré-traitement :**
- Toujours appelé (WebUI ET API)
- Reçoit les données modifiées par les filtres précédents
- Peut injecter des paramètres body supplémentaires (sauf clés réservées : metadata, features, tool_ids, files, skill_ids)
- DOIT retourner body

**`stream()` — Interception temps réel :**
- Toujours appelé (WebUI ET API)
- Opère sur les chunks individuels pendant le streaming
- Structure de l'event : `{"id": "chatcmpl-...", "choices": [{"delta": {"content": "text fragment"}}]}`

**`outlet()` — Post-traitement :**
- **NON appelé** pour les requêtes API directes à `/api/chat/completions`
- Appelé après complétion chat WebUI
- Retourne None (basé sur effets de bord)
- Pour déclencher via API : `POST /api/chat/completed`

### Comportement API :
```
inlet()    → ✅ Toujours appelé (WebUI + API)
stream()   → ✅ Toujours appelé (WebUI + API)
outlet()   → ❌ NON appelé pour requêtes API directes
```

### Système global/spécifique modèle :

| État | is_active | is_global | Effet |
|------|-----------|-----------|-------|
| Globalement activé | ✅ True | ✅ True | S'applique à TOUS les modèles (grisé) |
| Globalement désactivé | ❌ False | Any | Pas appliqué |
| Spécifique modèle | ✅ True | ❌ False | Seulement sur les modèles sélectionnés |
| Inactif | ❌ False | ❌ False | Pas appliqué |

### Toggleable vs Always-On :
- **Toggleable (`toggle=True`)** : switches dans l'UI, activation/désactivation par l'utilisateur par session
- **Always-On (pas de toggle)** : s'exécute automatiquement, pas de contrôle utilisateur, idéal pour sécurité/compliance/logging

## 6.4 Action Function (boutons interactifs)

### Structure de base :
```python
class Action:
    class Valves(BaseModel):
        parameter_name: str = "default_value"
        priority: int = 0  # Contrôle l'ordre d'affichage des boutons
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def action(self, body: dict, __user__=None, __event_emitter__=None,
                     __event_call__=None, __model__=None, __request__=None, __id__=None):
        return {"content": "Modified message content"}
```

**Source :** https://docs.openwebui.com/features/extensibility/plugin/functions/action/ — consultée le 13/04/2026

**Exigence critique :** "Action functions should always be defined as `async`."

### Multi-Actions :
```python
actions = [
    {"id": "summarize", "name": "Summarize", "icon_url": "https://example.com/icons/summarize.svg"},
    {"id": "translate", "name": "Translate", "icon_url": "https://example.com/icons/translate.svg"}
]

async def action(self, body: dict, __id__=None, **kwargs):
    if __id__ == "summarize":
        return {"content": "Summary: ..."}
    elif __id__ == "translate":
        return {"content": "Translation: ..."}
```

### Ordre des boutons :
"Action buttons beneath assistant messages are sorted by their `priority` valve value in **ascending order** — lower values appear first (leftmost)."
Sans valve priority : "their order among equal priorities is determined **alphabetically by function ID**."

### Frontmatter :
```python
"""
title: Enhanced Message Processor
author: @admin
version: 1.2.0
required_open_webui_version: 0.5.0
icon_url: https://example.com/icons/message-processor.svg
requirements: requests,beautifulsoup4
"""
```

**Champs supportés :** title, author, version, required_open_webui_version, icon_url (DOIT utiliser des URLs hébergées, jamais base64)

### Valeur de retour :
```python
{
    "content": "Modified message content",
    "files": [{"type": "image", "url": "generated_chart.png", "name": "Analysis Chart"}]
}
```

---

# CATÉGORIE 7 : RICH UI EMBEDDING

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Mécanisme | `HTMLResponse` avec header `Content-Disposition: inline` → affichage dans iframe sandboxé | https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ | consultée le 13/04/2026 |
| Disponibilité | Tools ✅, Actions ✅, Pipes ❌, Filters ❌ | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Position rendu | Tools : inline au tool call indicator ; Actions : au-dessus du texte du message | https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ | consultée le 13/04/2026 |

### Contenu détaillé — Implémentation Tool :
```python
from fastapi.responses import HTMLResponse

def create_visualization_tool(self, data: str) -> HTMLResponse:
    html_content = """<!DOCTYPE html><html>...</html>"""
    headers = {"Content-Disposition": "inline"}
    return HTMLResponse(content=html_content, headers=headers)
```

### Fournir du contexte au LLM (tuple) :
```python
def create_chart(self, data: str) -> tuple:
    html_content = "<html>...</html>"
    result_context = {"status": "success", "chart_type": "scatter", "data_points": 42}
    return HTMLResponse(content=html_content, headers=headers), result_context
```
Sans contexte custom, le LLM reçoit : "Tool name: Embedded UI result is active and visible to the user."

### Gestion hauteur iframe :
```javascript
// Via postMessage (recommandé quand allowSameOrigin est OFF)
function reportHeight() {
    const h = document.documentElement.scrollHeight;
    parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
new ResizeObserver(reportHeight).observe(document.body);
```

### Sandbox (flags toujours actifs) :
- `allow-scripts` — Exécution JavaScript
- `allow-popups` — window.open()
- `allow-downloads` — Téléchargements

### Sandbox (flags configurables par l'utilisateur) :
- "Allow Iframe Same-Origin Access" (Settings → Interface)
- "Allow Iframe Form Submissions"

### allowSameOrigin OFF (défaut) :
- Isolation complète, iframe ne peut pas accéder parent cookies/localStorage/DOM
- Requiert postMessage pour reporter la hauteur
- Configuration la plus sûre

### allowSameOrigin ON :
- iframe accède au contexte parent
- Auto-resize sans script
- Chart.js et Alpine.js auto-injectés si détectés
- Nécessite confiance dans le contenu embarqué

### Communication avancée — injection d'arguments :
```javascript
// Tools injectent automatiquement les paramètres dans window.args
window.addEventListener('load', () => {
    const args = window.args; // Paramètres JSON passés au tool
});
// Les Actions ne reçoivent PAS window.args
```

### Communication avancée — soumission de prompt :
| Type | Comportement |
|------|-------------|
| `input:prompt` | Remplit l'input sans soumettre |
| `input:prompt:submit` | Remplit et soumet |
| `action:submit` | Soumet le texte d'input courant |

```javascript
parent.postMessage({ type: 'input:prompt:submit', text: 'Show summary' }, '*');
```
Quand allowSameOrigin est OFF, `input:prompt:submit` affiche un dialogue de confirmation.

### Rich UI vs Execute Event :
| Aspect | Rich UI Embed | Execute Event |
|--------|---------------|---------------|
| Environnement | Iframe sandboxé | Page principale (non sandboxé) |
| Persistance | Sauvegardé dans l'historique | Éphémère, perdu au rechargement |
| Accès page | Isolé par défaut | Accès complet DOM/cookies/storage |
| Formulaires | Requiert allowForms | Toujours fonctionnel |
| Meilleur usage | Dashboards persistants, graphiques | Interactions transitoires, téléchargements |

**Source :** https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ — consultée le 13/04/2026

---

# CATÉGORIE 8 : MIGRATIONS ET BREAKING CHANGES

## 8.1 Migration 0.4 → 0.5.0

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Changement architectural | Sub-app architecture → single FastAPI app with multiple routers | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 | consultée le 13/04/2026 |
| Import paths | `open_webui.apps.*` → `open_webui.routers.*` (sauf `apps.webui` → `main`, `apps.webui.models` → `models`) | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 | consultée le 13/04/2026 |
| Nouveau paramètre obligatoire | `__request__: Request` dans toutes les fonctions pipe | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 | consultée le 13/04/2026 |
| Remplacement API | `openai.generate_chat_completion(form_data, user)` → `generate_chat_completion(__request__, form_data, user)` depuis `open_webui.utils.chat` | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.5.0 | consultée le 13/04/2026 |

### Avant / Après :
```python
# AVANT (0.4)
from open_webui.apps.ollama import generate_chat_completion
async def pipe(self, body: dict, __user__: dict) -> str:
    user = User(**__user__)
    return await generate_chat_completion(body, user)

# APRÈS (0.5)
from open_webui.utils.chat import generate_chat_completion
from fastapi import Request
async def pipe(self, body: dict, __user__: dict, __request__: Request) -> str:
    user = User(**__user__)
    return await generate_chat_completion(__request__, body, user)
```

## 8.2 Migration vers 0.9.0

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Changement core | Data layer passe de synchrone à asynchrone de bout en bout | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 | consultée le 13/04/2026 |
| Impact | Tous les model methods (Users, Chats, Files, Models, Functions, Tools, Knowledges) retournent des coroutines | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 | consultée le 13/04/2026 |
| Sessions BDD | `get_db_context` sync supprimé → `get_async_db_context` avec `AsyncSession` et SQLAlchemy 2.0 async | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 | consultée le 13/04/2026 |
| Propagation async | "once one function in the chain becomes a coroutine, every caller does too, all the way up to your plugin's entrypoint" | https://docs.openwebui.com/features/extensibility/plugin/migration/to-0.9.0 | consultée le 13/04/2026 |

### Avant / Après :
```python
# AVANT (0.8.x)
def resolve_user(user_id: str):
    user = Users.get_user_by_id(user_id)
    chats = Chats.get_chat_list_by_user_id(user_id)
    return user, chats

# APRÈS (0.9.0)
async def resolve_user(user_id: str):
    user = await Users.get_user_by_id(user_id)
    chats = await Chats.get_chat_list_by_user_id(user_id)
    return user, chats
```

### Patterns de requête changés :
- `.first()` → `.scalars().first()`
- `.all()` → `.scalars().all()`
- `.count()` → `.scalar_one()`

### Pour les dépendances sync :
```python
import anyio
result = await anyio.to_thread.run_sync(legacy_client.fetch, url)
```

---

# CATÉGORIE 9 : SÉCURITÉ

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Exécution arbitraire | "Workspace Tools and Functions execute arbitrary Python code on your server" | https://docs.openwebui.com/features/extensibility/plugin/tools/development/ | consultée le 13/04/2026 |
| Équivalence shell | "Granting a user the ability to create or import Tools is equivalent to giving them shell access" | https://docs.openwebui.com/features/extensibility/plugin/tools/development/ | consultée le 13/04/2026 |
| Restriction création | Création de fonctions/tools restreinte aux administrateurs | https://docs.openwebui.com/features/extensibility/plugin/ | consultée le 13/04/2026 |
| Répertoire données | `/app/backend/data` dans Docker | https://docs.openwebui.com/features/extensibility/plugin/ | consultée le 13/04/2026 |
| Execute JS non sandboxé | "JavaScript runs in main page context with full DOM, cookie, and localStorage access—no iframe sandboxing" (pour les events execute) | https://docs.openwebui.com/features/extensibility/plugin/development/events | consultée le 13/04/2026 |
| Risques Pipelines | "A malicious Pipeline could access your file system, exfiltrate data, mine cryptocurrency, or compromise your system" | https://docs.openwebui.com/features/extensibility/pipelines/ | consultée le 13/04/2026 |

---

# CATÉGORIE 10 : SCHÉMA DE BASE DE DONNÉES

## 10.1 Table `function`

```python
class Function(Base):
    __tablename__ = 'function'
    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String)
    name = Column(Text)
    type = Column(Text)  # "pipe", "filter", "action"
    content = Column(Text)  # Code Python source
    meta = Column(JSONField)  # {description, manifest}
    valves = Column(JSONField)  # Configuration admin
    is_active = Column(Boolean)
    is_global = Column(Boolean)
    updated_at = Column(BigInteger)  # epoch timestamp
    created_at = Column(BigInteger)
    # Index sur is_global
```

**Source :** https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/functions.py — consultée le 13/04/2026

### Modèles Pydantic associés :
- **FunctionModel** : Représentation complète
- **FunctionWithValvesModel** : Avec valves optionnelles
- **FunctionResponse** : Pour API, exclut le champ content
- **FunctionForm** : Input (id, name, content, meta requis)

### Méthodes CRUD principales :
- `insert_new_function()` : Création avec timestamps auto
- `sync_functions()` : Synchronisation batch (update existing, insert new, delete obsolete)
- `get_function_by_id()` : Lecture
- `get_functions_by_type()` : Filtrage par type
- `get_global_filter_functions()` : Filtres globaux actifs
- `get_global_action_functions()` : Actions globales actives
- `get_function_valves_by_id()` : Récupération valves
- `get_user_valves_by_id_and_user_id()` : Valves utilisateur (stockées dans user settings)
- `update_function_valves_by_id()` : Mise à jour valves

## 10.2 Table `tool`

```python
class Tool(Base):
    __tablename__ = 'tool'
    id = Column(String, primary_key=True, unique=True)
    user_id = Column(String)
    name = Column(Text)
    content = Column(Text)  # Code Python source
    specs = Column(JSONField)  # JSON schema des fonctions du tool
    meta = Column(JSONField)  # {description, manifest}
    valves = Column(JSONField)
    updated_at = Column(BigInteger)
    created_at = Column(BigInteger)
```

**Source :** https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/tools.py — consultée le 13/04/2026

### Modèles Pydantic associés :
- **ToolModel** : Avec access_grants
- **ToolUserModel** : Avec UserResponse
- **ToolAccessResponse** : Avec write_access boolean
- **ToolForm** : Input (id, name, content, meta, access_grants optionnel)

### Contrôle d'accès :
- `_get_access_grants()` : Récupère les grants d'accès
- `get_tools_by_user_id()` : Filtre par propriété OU permission d'accès

---

# CATÉGORIE 11 : BUILT-IN SYSTEM TOOLS (Native Mode uniquement)

| Catégorie | Outils | Description |
|-----------|--------|-------------|
| Search & Web | `search_web`, `fetch_url` | Requêtes web, extraction contenu URL |
| Knowledge Base | `list_knowledge`, `query_knowledge_files`, `view_file`, etc. | Navigation et extraction depuis les KB |
| Memory | `search_memories`, `add_memory`, `delete_memory` | Gestion de la personnalisation |
| Notes | `search_notes`, `write_note`, `view_note` | Opérations sur les notes utilisateur |
| Chat History | `search_chats`, `view_chat` | Accès historique conversations |
| Code Interpreter | `execute_code` | Exécution de code sandboxée |
| Image Generation | `generate_image`, `edit_image` | Création et modification d'images |
| Channels | `search_channels`, `view_channel_message` | Opérations sur les canaux |
| Time Tools | `get_current_timestamp`, `calculate_timestamp` | Calculs temporels |

**Source :** https://docs.openwebui.com/features/extensibility/plugin/tools/ — consultée le 13/04/2026

**Exemple de signature :** `query_knowledge_files(query, knowledge_ids?, count=5)` → Retourne `Array of {content, source, file_id, distance?}`

**Contrôle d'accès :** "Attached workspace tool to a model does not bypass access control. When a user chats, Open WebUI checks whether that specific user has read access to each attached tool."

---

# DONNÉES NON TROUVÉES (Lot 1)

| Donnée recherchée | Statut | Commentaire |
|--------------------|--------|-------------|
| URL page Events (originale) | 404 sur https://docs.openwebui.com/features/plugin/development/events/ | Trouvée à https://docs.openwebui.com/features/extensibility/plugin/development/events (sans slash final) |
| Page Special Arguments | 404 sur https://docs.openwebui.com/tutorials/tips/special_arguments/ | Contenu équivalent trouvé dans reserved-args |
| Documentation Pipelines Pipes détaillée | Page superficielle sans code | https://docs.openwebui.com/features/extensibility/pipelines/pipes/ manque de spécifications techniques détaillées |
| Code source complet de functions.py | Résumé par WebFetch, pas le code brut complet | Résumé structurel suffisant pour le corpus |

---

*Fin du Lot 1 — Sources 1 à 4*
*Prêt pour le Lot 2 (Sources 5 à 7) sur validation*