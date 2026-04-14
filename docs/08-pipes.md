# Créer un Pipe (modèle/agent custom)

Un Pipe Function se présente comme un **modèle autonome** dans l'interface Open WebUI. L'utilisateur le sélectionne comme n'importe quel autre modèle, et le Pipe traite la requête avec sa logique custom.

## Structure de base

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
        pass
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ — consultée le 13/04/2026

## Méthode `pipe()`

C'est la méthode principale appelée quand l'utilisateur envoie un message au modèle Pipe.

### Paramètres

| Paramètre | Type | Obligatoire | Description |
|-----------|------|-------------|-------------|
| `body` | dict | Oui | Payload de la requête (model, stream, messages, etc.) |
| `__user__` | dict | Non | Informations utilisateur |
| `__request__` | Request | **Oui depuis 0.5.0** | Objet Request FastAPI |
| `__event_emitter__` | Callable | Non | Communication one-way vers le frontend |
| `__event_call__` | Callable | Non | Communication bidirectionnelle avec l'utilisateur |
| `__metadata__` | dict | Non | Métadonnées de contexte enrichies |
| `__messages__` | list | Non | Liste des messages (identique à `body["messages"]`) |
| `__files__` | list | Non | Liste d'objets fichiers |
| `__model__` | dict | Non | Objet modèle complet |
| `__tools__` | list | Non | Liste d'instances ToolUserModel (pour appeler d'autres outils) |
| `__chat_id__` | str | Non | UUID de la conversation |
| `__session_id__` | str | Non | Identifiant de session |
| `__message_id__` | str | Non | Identifiant du message courant |

> **Breaking change v0.5.0 :** `__request__` est devenu obligatoire. Sans lui, les appels à `generate_chat_completion` et autres fonctions internes ne fonctionneront pas.

### Retour

La méthode `pipe()` peut retourner :
- `str` — réponse texte simple
- `Generator` / `Iterator` — pour le streaming
- `AsyncGenerator` — pour le streaming async
- Dict au format OpenAI chat completion

### Streaming

```python
if body.get("stream", False):
    return r.iter_lines()  # Iterator pour streaming
else:
    return r.json()  # Réponse complète
```

## Méthode `pipes()` — Pattern Manifold

La méthode `pipes()` retourne une liste de modèles. Chaque entrée apparaît comme un modèle sélectionnable dans l'interface. Le modèle sélectionné est routé via `body["model"]`.

```python
def pipes(self) -> list:
    return [
        {"id": "model-1", "name": "Display Name 1"},
        {"id": "model-2", "name": "Display Name 2"}
    ]
```

L'ID du modèle sélectionné est disponible dans `body["model"]` sous la forme `pipe_id.sub_id` (ex: `my_pipe.model-1`).

### Pipe sans `pipes()`

Si la méthode `pipes()` n'est pas définie, le Pipe apparaît dans l'UI comme un **modèle unique** avec le nom du Pipe (`self.name`). C'est le cas le plus simple pour un Pipe qui ne gère qu'un seul modèle.

### Utilisation de `__tools__` dans un Pipe

Un Pipe peut accéder aux outils disponibles via le paramètre `__tools__` pour appeler d'autres outils :

```python
async def pipe(self, body: dict, __tools__=None, __user__=None, __request__=None) -> str:
    if __tools__:
        for tool in __tools__:
            if tool.get("name") == "search_tool":
                result = await tool["callable"]("search query")
                # Utiliser le résultat...
    return "Response based on tool output"
```

> **Attention sécurité :** Pour les outils async, `tool["callable"]` est un `functools.partial` qui peut exposer des données sensibles. Voir [13-security.md](13-security.md).

### Manifold dans les Pipelines externes

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

## Accès aux fonctions internes Open WebUI

Un Pipe peut appeler des fonctions internes d'Open WebUI :

```python
from open_webui.models.users import Users
from open_webui.utils.chat import generate_chat_completion

# v0.9.0+ : async
user_obj = await Users.get_user_by_id(__user__["id"])
result = await generate_chat_completion(__request__, body, user_obj)
```

### Avant v0.9.0 (sync)

```python
user_obj = Users.get_user_by_id(__user__["id"])
result = await generate_chat_completion(__request__, body, user_obj)
```

## Pipeline Scaffolds — Hooks de cycle de vie

Les Pipelines externes disposent de hooks supplémentaires :

```python
class Pipeline:
    async def on_startup(self):
        print(f"on_startup:{__name__}")

    async def on_shutdown(self):
        print(f"on_shutdown:{__name__}")

    async def on_valves_updated(self):
        pass
```

> Source : https://github.com/open-webui/pipelines/blob/main/examples/scaffolds/example_pipeline_scaffold.py — consultée le 13/04/2026
