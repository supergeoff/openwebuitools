# Créer un Filter (pré/post-traitement)

Un Filter Function agit comme middleware dans le flux de traitement. Il peut modifier les données en entrée (`inlet`), intercepter le streaming (`stream`), et modifier les données en sortie (`outlet`).

## Structure de base

```python
from pydantic import BaseModel, Field
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

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ — consultée le 13/04/2026

## Méthodes

### `inlet()` — Pré-traitement

- **Toujours appelé** (WebUI ET API)
- Reçoit les données modifiées par les filtres précédents (les Filters s'exécutent en cascade selon leur `priority`)
- Peut injecter des paramètres body supplémentaires
- **Clés réservées non modifiables :** `metadata`, `features`, `tool_ids`, `files`, `skill_ids`
- **DOIT retourner body**

```python
async def inlet(self, body: dict, __event_emitter__=None, __user__=None, __metadata__=None, __model__=None) -> dict:
    # Exemple : filtrer des mots indésirables
    user_message = body["messages"][-1]["content"]
    body["messages"][-1]["content"] = user_message.replace("bad_word", "[filtered]")
    return body
```

### `stream()` — Interception temps réel

- **Toujours appelé** (WebUI ET API)
- Opère sur les chunks individuels pendant le streaming
- Peut être async (`async def stream(self, event: dict) -> dict`)
- Structure de l'event :

```python
{
    "id": "chatcmpl-...",
    "choices": [{"delta": {"content": "text fragment"}}]
}
```

```python
def stream(self, event: dict) -> dict:
    # Exemple : transformer le texte en streaming
    if "choices" in event and event["choices"]:
        content = event["choices"][0].get("delta", {}).get("content", "")
        event["choices"][0]["delta"]["content"] = content.upper()
    return event
```

### `outlet()` — Post-traitement

- **NON appelé** pour les requêtes API directes à `/api/chat/completions`
- Appelé après complétion chat WebUI uniquement
- Peut être sync ou async
- Retourne `None` (basé sur effets de bord) ou `body` modifié (retourner `body` modifié peut fonctionner mais le comportement a été affecté par le bug #8168 — désormais résolu)
- Pour déclencher via API : `POST /api/chat/completed`

```python
async def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
    # Log, audit, notification...
    pass
```

## Comportement API

| Méthode | WebUI | API directe `/api/chat/completions` |
|---------|-------|-------------------------------------|
| `inlet()` | ✅ Toujours appelé | ✅ Toujours appelé |
| `stream()` | ✅ Toujours appelé | ✅ Toujours appelé |
| `outlet()` | ✅ Appelé | ❌ NON appelé |

## Système global / spécifique modèle

| État | is_active | is_global | Effet |
|------|-----------|-----------|-------|
| Globalement activé | ✅ True | ✅ True | S'applique à TOUS les modèles (grisé dans l'UI) |
| Globalement désactivé | ❌ False | Any | Pas appliqué |
| Spécifique modèle | ✅ True | ❌ False | Seulement sur les modèles sélectionnés |
| Inactif | ❌ False | ❌ False | Pas appliqué |

## Toggleable vs Always-On

### Toggleable (`self.toggle = True`)

- Switches visibles dans l'UI
- Activation/désactivation par l'utilisateur par session
- Idéal pour les filtres optionnels (ex: traduction, prompt enhancement)

### Always-On (pas de `self.toggle`)

- S'exécute automatiquement
- Pas de contrôle utilisateur
- Idéal pour sécurité, compliance, logging

## `self.icon`

URL de l'icône affichée dans l'interface pour le Filter.

## Exemple complet : filtre de mots

```python
from pydantic import BaseModel, Field
from typing import Optional
import re

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Lower values execute first")
        blocked_words: str = Field(default="bad1,bad2,bad3", description="Comma-separated words to filter")
    
    def __init__(self):
        self.valves = self.Valves()
        self.toggle = True
    
    async def inlet(self, body: dict, __user__=None) -> dict:
        words = [w.strip() for w in self.valves.blocked_words.split(",")]
        content = body["messages"][-1]["content"]
        for word in words:
            content = re.sub(rf'\b{re.escape(word)}\b', '[filtered]', content, flags=re.IGNORECASE)
        body["messages"][-1]["content"] = content
        return body
    
    def outlet(self, body: dict, __user__: Optional[dict] = None) -> None:
        pass
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ + article Medium — consultée le 13/04/2026

## Leçons de bugs connus

### `__event_emitter__` dans outlet (Issue #8168 — RÉSOLU)

Le typage du paramètre `__event_emitter__` doit être `Callable` ou omis (pour l'injection automatique), **pas `None`**. Le comportement de revert dans outlet était un bug résolu.

```python
# INCORRECT
async def outlet(self, body: dict, __event_emitter__: None) -> dict:

# CORRECT
async def outlet(self, body: dict, __event_emitter__=None) -> dict:
```

> Source : Issue #8168 — consultée le 13/04/2026

## Filtres dans le contexte Pipelines

Dans le contexte des Pipelines externes, les filtres ont des propriétés spécifiques :

```python
class Pipeline:
    def __init__(self):
        self.type = "filter"  # Requis pour que le Pipeline soit traité comme filtre
        self.name = "Filter"
        self.valves = self.Valves(**{"pipelines": ["llama3:latest"]})
    
    class Valves(BaseModel):
        pipelines: List[str] = []  # Cibler des pipelines spécifiques
        priority: int = 0
```

La valve `pipelines` permet de cibler uniquement certains pipelines. Si vide, le filtre s'applique à tous les pipelines.
