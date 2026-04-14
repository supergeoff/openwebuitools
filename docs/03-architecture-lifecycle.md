# Architecture technique et cycle de vie

## Flux de données global

```
User Input → Inlet Filters → RAG Query → LLM Call → Outlet Filters → UI Display
                ↓                                          ↓
           Pré-traitement                           Post-traitement
```

> Source : https://deepwiki.com/open-webui/docs/4.2-functions-system — consultée le 13/04/2026
>
> **Avertissement :** DeepWiki est une source IA-générée dont la fiabilité est limitée. Le schéma de flux ci-dessus a été vérifié contre le code source mais peut contenir des approximations.

## Cycle de vie d'une Function custom

### Stockage

Table `function` en base de données :

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | String (PK) | Identifiant unique |
| `user_id` | String | Créateur |
| `name` | Text | Nom d'affichage |
| `type` | Text | `"pipe"`, `"filter"` ou `"action"` |
| `content` | Text | Code Python source |
| `meta` | JSONField | `{description, manifest}` |
| `valves` | JSONField | Configuration admin |
| `is_active` | Boolean | Activée ou non |
| `is_global` | Boolean | S'applique à tous les modèles |
| `updated_at` | BigInteger | Epoch timestamp |
| `created_at` | BigInteger | Epoch timestamp |

> Source : https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/functions.py — consultée le 13/04/2026

### Modèles Pydantic associés

- **FunctionModel** : Représentation complète
- **FunctionWithValvesModel** : Avec valves optionnelles
- **FunctionResponse** : Pour API, exclut le champ content
- **FunctionForm** : Input (id, name, content, meta requis)

### Méthodes CRUD principales

| Méthode | Rôle |
|---------|------|
| `insert_new_function()` | Création avec timestamps auto |
| `sync_functions()` | Synchronisation batch (update existing, insert new, delete obsolete) |
| `get_function_by_id()` | Lecture |
| `get_functions_by_type()` | Filtrage par type |
| `get_global_filter_functions()` | Filtres globaux actifs |
| `get_global_action_functions()` | Actions globales actives |
| `get_function_valves_by_id()` | Récupération valves |
| `get_user_valves_by_id_and_user_id()` | Valves utilisateur (stockées dans user settings) |
| `update_function_valves_by_id()` | Mise à jour valves |
| `_get_access_grants()` | Lecture des droits d'accès d'une fonction |
| `get_tools_by_user_id()` | Outils accessibles par un utilisateur donné |

### Chargement et exécution

| Étape | Fonction | Description |
|-------|----------|-------------|
| Chargement module | `get_function_module_by_id(request, pipe_id)` | Récupère le module avec cache, initialise les Valves depuis la BDD |
| Énumération modèles Pipe | `get_function_models(request)` | Énumère toutes les fonctions pipe actives, gère les manifolds (pipes multiples), génère des IDs composites `pipe.id.sub_id` |
| Exécution principale | `generate_function_chat_completion(request, form_data, user, models)` | Extrait metadata, construit `extra_params` avec les paramètres injectés, charge le module, exécute le pipe |
| Injection de paramètres | `get_function_params(function_module, form_data, user, extra_params)` | Utilise `inspect.signature()` pour matcher extra_params avec les paramètres déclarés par la fonction |
| Exécution pipe | `execute_pipe(pipe, params)` | Détecte si la fonction est async ou sync, exécute avec les paramètres injectés |
| Réponse streaming | Si `form_data['stream']` est True | Réponses wrappées dans `StreamingResponse` au format event-stream. Supporte : string, Generator sync, AsyncGenerator |

> Source : https://raw.githubusercontent.com/open-webui/open-webui/main/backend/open_webui/functions.py — consultée le 13/04/2026

## Cycle de vie d'un Tool

### Stockage

Table `tool` en base de données :

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | String (PK) | Identifiant unique |
| `user_id` | String | Créateur |
| `name` | Text | Nom d'affichage |
| `content` | Text | Code Python source |
| `specs` | JSONField | JSON schema des fonctions du tool |
| `meta` | JSONField | `{description, manifest}` |
| `valves` | JSONField | Configuration admin |
| `updated_at` | BigInteger | Epoch timestamp |
| `created_at` | BigInteger | Epoch timestamp |

> Source : https://github.com/open-webui/open-webui/blob/main/backend/open_webui/models/tools.py — consultée le 13/04/2026

### Modèles Pydantic associés

- **ToolModel** : Avec access_grants
- **ToolUserModel** : Avec UserResponse
- **ToolAccessResponse** : Avec write_access boolean
- **ToolForm** : Input (id, name, content, meta, access_grants optionnel)

### Chargement

`get_tools()` dans `utils/tools.py` — vérifie le contrôle d'accès, charge les modules, applique les Valves, injecte les paramètres, gère les collisions de noms.

### Types de Tools

| Type | Description |
|------|-------------|
| Builtin | Hardcoded : search, code, memory |
| Local | BDD + plugin loader |
| OpenAPI | Serveurs externes |
| Terminal | CLI |

> Source : https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py — consultée le 13/04/2026

### Injection invisible des paramètres

`get_async_tool_function_and_apply_extra_params()` — wrappe les fonctions pour injecter `__id__`, `__user__`, etc. tout en les masquant de la signature visible par le modèle.

> Source : https://github.com/open-webui/open-webui/blob/main/backend/open_webui/utils/tools.py — consultée le 13/04/2026

### Contrôle d'accès des Tools

3 niveaux :

| Niveau | Description |
|--------|-------------|
| Bypass admin | Les administrateurs contournent les restrictions |
| Propriétaire (creator-only) | Seul le créateur peut utiliser le tool |
| Group-based grants | Accès par groupes d'utilisateurs |

> "Attached workspace tool to a model does not bypass access control. When a user chats, Open WebUI checks whether that specific user has read access to each attached tool."
>
> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/ — consultée le 13/04/2026

## Pipeline Scaffolds (Pipelines externes)

Les Pipelines disposent de hooks de cycle de vie spécifiques :

| Hook | Description |
|------|-------------|
| `on_startup()` | Appelé au démarrage du serveur |
| `on_shutdown()` | Appelé à l'arrêt du serveur |
| `on_valves_updated()` | Appelé quand les valves sont mises à jour |

### Exemple scaffold Pipeline basique

```python
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from schemas import OpenAIChatMessage  # Uniquement disponible dans le contexte Pipelines, pas dans Open WebUI main

class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.name = "Pipeline Example"
        pass

    async def on_startup(self):
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")
        pass

    async def on_valves_updated(self):
        pass

    async def inlet(self, body: dict, user: dict) -> dict:
        return body

    async def outlet(self, body: dict, user: dict) -> dict:
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        if body.get("title", False):
            print("Title Generation Request")
        return f"{__name__} response to: {user_message}"
```

> Source : https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/example_pipeline_scaffold.py — consultée le 13/04/2026

### Exemple scaffold Filter Pipeline

```python
"""
title: Filter Pipeline
author: Open WebUI
date: 2024-01-01
version: 1.0.0
license: MIT
description: A filter pipeline example
requirements: detoxify
"""

from typing import List, Optional
from pydantic import BaseModel

class Pipeline:
    class Valves(BaseModel):
        pipelines: List[str] = []
        priority: int = 0

    def __init__(self):
        self.type = "filter"
        self.name = "Filter"
        self.valves = self.Valves(**{"pipelines": ["llama3:latest"]})

    async def inlet(self, body: dict, user: Optional[dict] = None) -> dict:
        if body.get("title", False):
            print("Title Generation Request")
        return body
```

> Source : https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/filter_pipeline_scaffold.py — consultée le 13/04/2026

### Exemple scaffold Manifold Pipeline

```python
class Pipeline:
    def __init__(self):
        self.type = "manifold"
        self.name = "Manifold: "
        self.pipelines = [
            {"id": "pipeline-1", "name": "Pipeline 1"},
            {"id": "pipeline-2", "name": "Pipeline 2"},
        ]

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        return f"{model_id} response to: {user_message}"
```

> Source : https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/manifold_pipeline_scaffold.py — consultée le 13/04/2026

### Exemple scaffold Function Calling Pipeline

```python
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel

class Pipeline:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"
        self.name = "Function Calling: "
        self.pipes = [
            {"id": "function-calling", "name": "Function Calling"},
        ]

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # Le function calling scaffold démontre comment exposer
        # un pipeline avec support natif du function calling
        return f"{model_id} response to: {user_message}"
```

> Source : https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/function_calling_scaffold.py — consultée le 13/04/2026
