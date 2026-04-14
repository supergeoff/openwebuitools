# Paramètres injectés (API implicite)

Open WebUI injecte automatiquement certains paramètres dans les fonctions d'extension. Le mécanisme utilise `inspect.signature()` pour matcher les paramètres déclarés par la fonction avec les `extra_params` disponibles. Il suffit de **déclarer le paramètre dans la signature** pour le recevoir.

## Référence complète des paramètres réservés

| Paramètre | Type | Toujours disponible | Description |
|-----------|------|---------------------|-------------|
| `body` | dict | Oui | Dictionnaire de la requête de chat completion : stream, model, messages, features, stream_options, metadata, files |
| `__user__` | dict | Oui | `{id, email, name, role ("user"\|"admin"), valves (si UserValves défini)}` |
| `__metadata__` | dict | Oui | Métadonnées de contexte enrichies (voir structure ci-dessous) |
| `__model__` | dict | Oui | Objet modèle complet (voir structure ci-dessous) |
| `__messages__` | list | Oui | Liste des messages, identique à `body["messages"]` |
| `__chat_id__` | str | Contexte chat | UUID unique de la conversation |
| `__session_id__` | str | Généralement | Identifiant de session |
| `__message_id__` | str | Contexte chat | Identifiant du message courant |
| `__event_emitter__` | Callable | Contexte fonction | Communication one-way vers le frontend |
| `__event_call__` | Callable | Contexte fonction | Communication bidirectionnelle, timeout 300s (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`). Disponible dans Tools, Actions, Pipes et Filters. |
| `__files__` | list | Oui ([] si vide) | Liste d'objets fichiers (voir structure ci-dessous) |
| `__request__` | fastapi.Request | Oui | Instance Request FastAPI |
| `__task__` | str | Contexte tâche | Type de tâche interne |
| `__task_body__` | dict | Contexte tâche | Body spécifique à la tâche interne |
| `__tools__` | list | Oui | Liste d'instances ToolUserModel (voir structure ci-dessous) |
| `__id__` | str | Actions | Identifiant de l'action (utile pour multi-actions) |
| `__oauth_token__` | dict | Si configuré | Token OAuth de l'utilisateur (auto-refreshed). Méthode recommandée pour les appels API authentifiés (voir structure ci-dessous) |

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/reserved-args — consultée le 13/04/2026

## Structure de `__metadata__`

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
        "image_generation": False,
        "code_interpreter": False,
        "web_search": False
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
    "direct": False,
    "function_calling": "native",
    "type": "user_response",
    "interface": "open-webui|other"
}
```

### Types de tâches internes (`__task__`)

`title_generation`, `tags_generation`, `emoji_generation`, `query_generation`, `image_prompt_generation`, `autocomplete_generation`, `function_calling`, `moa_response_generation`

### Détection de la source de la requête

```python
if __metadata__ and __metadata__.get("interface") == "open-webui":
    # Requête depuis l'interface web
else:
    # Requête API directe
```

## Structure de `__model__`

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
            "capabilities": {"vision": True, "usage": True, "citations": True},
            "position": 17,
            "tags": [{"name": "tag_name"}],
            "suggestion_prompts": None
        },
        "access_control": {
            "read": {"group_ids": [], "user_ids": []},
            "write": {"group_ids": [], "user_ids": []}
        },
        "is_active": True,
        "updated_at": 1740000000,
        "created_at": 1740000000
    },
    "preset": True,
    "actions": [],
    "tags": [{"name": "tag_name"}]
}
```

## Structure de `__files__`

Les images sont exclues de `__files__` — elles sont envoyées en base64 directement dans les messages.

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

### Accès au fichier physique

```python
from pathlib import Path
the_file = Path(f"/app/backend/data/uploads/{__files__[0]['file']['id']}_{__files__[0]['file']['filename']}")
assert the_file.exists()
```

## Structure de `__tools__`

Chaque élément de `__tools__` est un `ToolUserModel` contenant :

```python
{
    "id": "uuid",
    "user_id": "uuid",
    "name": "Tool Display Name",
    "content": "# Code source Python...",
    "specs": [{...}],  # JSON schema des fonctions du tool
    "meta": {"description": "...", "manifest": {...}},
    "valves": {...},
    "access_control": {...},
    "user": {"id": "uuid", "name": "...", "email": "...", "role": "..."},
    "callable": <function ou functools.partial>,
    "# ... autres champs du modèle Tool"
}
```

> **Attention sécurité :** Pour les outils async, le champ `callable` est un `functools.partial` qui peut exposer des données sensibles (`__user__`, `__event_emitter__`). Voir [13-security.md](13-security.md) § fuite functools.partial.

## Structure de `__oauth_token__`

```python
{
    "access_token": "eyJ...",
    "token_type": "Bearer",
    "refresh_token": "...",  # Si supporté par le provider
    "expires_at": 1740000000  # Timestamp Unix, auto-refreshed
}
```

> Méthode recommandée pour les appels API authentifiés : utiliser `__oauth_token__["access_token"]` dans les headers Authorization plutôt que de stocker des clés API dans les Valves.

## Comportement quand un paramètre réservé est indisponible

Quand un paramètre réservé est demandé dans la signature mais n'est pas disponible dans le contexte actuel (ex: `__event_call__` sans connexion WebSocket live, `__oauth_token__` sans OAuth configuré), la valeur injectée est **`None`**. Aucune erreur n'est levée — il incombe au développeur de vérifier la disponibilité :

```python
async def my_tool(self, query: str, __event_call__=None) -> str:
    if __event_call__ is None:
        return "Mode dégradé : interaction bidirectionnelle non disponible"
    result = await __event_call__({...})
```
