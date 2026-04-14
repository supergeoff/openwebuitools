# Créer une Action (boutons interactifs)

Une Action Function ajoute des boutons interactifs sous les messages assistant dans l'interface. Au clic, du Python s'exécute côté serveur avec communication bidirectionnelle via `__event_call__`.

## Structure de base

```python
from pydantic import BaseModel, Field

class Action:
    class Valves(BaseModel):
        parameter_name: str = "default_value"
        priority: int = 0

    def __init__(self):
        self.valves = self.Valves()
    
    async def action(self, body: dict, __user__=None, __event_emitter__=None,
                     __event_call__=None, __model__=None, __request__=None, __id__=None,
                     __metadata__=None, __chat_id__=None, __message_id__=None):
        return {"content": "Modified message content"}
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/action/ — consultée le 13/04/2026

**Exigence critique :** "Action functions should always be defined as `async`."

## Multi-Actions

Une seule classe Action peut exposer plusieurs boutons via la liste `actions`, définie comme **attribut de classe** (au même niveau que `Valves`) :

```python
class Action:
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

Le paramètre `__id__` contient l'ID de l'action cliquée.

## Ordre des boutons

"Action buttons beneath assistant messages are sorted by their `priority` valve value in **ascending order** — lower values appear first (leftmost)."

Sans valve `priority`, l'ordre parmi les priorités égales est déterminé **alphabétiquement par function ID**.

## Frontmatter

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

**Champs supportés :** title, author, version, required_open_webui_version, icon_url

**ATTENTION :** `icon_url` DOIT utiliser des URLs hébergées, **jamais base64**.

## Valeur de retour — 3 comportements distincts

```python
# Cas 1 : Retourner None — ne PAS modifier le message (recommandé par défaut)
async def action(self, body: dict, **kwargs):
    # ... logique (notification, sauvegarde fichier, etc.)
    return None

# Cas 2 : Retourner {"content": "..."} — REMPLACER le contenu du message
async def action(self, body: dict, **kwargs):
    return {"content": "Modified message content",
            "files": [{"type": "image", "url": "chart.png", "name": "Chart"}]}

# Cas 3 : Retourner body — SUPPRIME le message (BUG, ne jamais faire)
async def action(self, body: dict, **kwargs):
    return body  # ← INCORRECT — cause la suppression non intentionnelle du message
```

> Source : Issue #8292 — consultée le 13/04/2026

## Exemple complet : sauvegarde de fichier

```python
async def action(self, body: dict, __user__=None, 
                __event_emitter__=None, __event_call__=None) -> None:
    response = await __event_call__({
        "type": "input",
        "data": {"title": "Filename", "message": "Enter filename", "placeholder": "output.txt"}
    })
    
    last_message = body["messages"][-1]["content"]
    
    with open(f"/app/data/{response}", "w") as f:
        f.write(last_message)
    
    await __event_emitter__({
        "type": "notification",
        "data": {"type": "success", "content": f"Saved to {response}"}
    })
```

> Source : Article Medium "Optimize Open WebUI" — consultée le 13/04/2026

## Configuration Docker pour la persistance fichiers

Les Actions qui écrivent des fichiers nécessitent un bind mount :

```bash
docker run -d -p 3000:8080 --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --mount type=bind,source="<local_path>",target=/app/data \
  --name open-webui ghcr.io/open-webui/open-webui:cuda
```

Le bind mount "enables data exchange between isolated container and host system."
