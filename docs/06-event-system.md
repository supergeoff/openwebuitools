# Système d'événements

Le système d'événements permet la communication entre le backend (votre code Python) et le frontend (l'interface utilisateur). Deux mécanismes complémentaires existent.

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/events — consultée le 13/04/2026

## `__event_emitter__` — Communication one-way

Backend → Frontend. Envoi d'événements sans attendre de réponse.

```python
await __event_emitter__({"type": "event_type", "data": {...}})
```

**Disponibilité :** Tools ✅, Actions ✅, Pipes ✅, Filters ✅

## `__event_call__` — Communication bidirectionnelle

Backend → Frontend → Backend. Attend la réponse de l'utilisateur.

**Timeout par défaut :** 300 secondes (configurable via `WEBSOCKET_EVENT_CALLER_TIMEOUT`)

**Disponibilité :** Tools ✅, Actions ✅, Pipes ✅, Filters ✅

## Référence complète des types d'événements

| Type | Helper | Data Structure | Persisté en BDD |
|------|--------|----------------|------------------|
| `status` | `__event_emitter__` | `{description: str, done: bool, hidden: bool}` | Oui (statusHistory) |
| `chat:message:delta` / `message` | `__event_emitter__` | `{content: str}` | `message` oui (content), `chat:message:delta` non |
| `chat:message` / `replace` | `__event_emitter__` | `{content: str}` | `replace` oui (content, écrase), `chat:message` non |
| `files` / `chat:message:files` | `__event_emitter__` | `{files: [...]}` | `files` oui |
| `chat:title` | `__event_emitter__` | `{title: str}` | Non (Socket.IO only) |
| `chat:tags` | `__event_emitter__` | `{tags: [...]}` | Non (Socket.IO only) |
| `source` / `citation` | `__event_emitter__` | Open WebUI Source/Citation Object (voir § Citations ci-dessous) | Oui (sources) |
| `embeds` / `chat:message:embeds` | `__event_emitter__` | `{embeds: [...]}` | `embeds` oui |
| `notification` | `__event_emitter__` | `{type: "info"\|"success"\|"warning"\|"error", content: str}` | Non (Socket.IO only) |
| `chat:message:error` | `__event_emitter__` | `{error: str}` | Non (Socket.IO only) |
| `chat:message:follow_ups` | `__event_emitter__` | `{follow_ups: [...]}` | Non (Socket.IO only) |
| `confirmation` | `__event_call__` | `{title: str, message: str}` | N/A (requiert connexion live) |
| `input` | `__event_call__` | `{title: str, message: str, placeholder: str, value: any, type: "password"\|optional}` | N/A (requiert connexion live) |
| `execute` | Les deux | `{code: "...javascript..."}` | Non |
| `chat:message:favorite` | `__event_emitter__` | `{favorite: bool}` | Non (Socket.IO only) |
| `chat:completion` | `__event_emitter__` | Custom | Non (Socket.IO only) |

## Persistance des événements

| Catégorie | Événements | Comportement |
|-----------|-----------|-------------|
| **Persistés en BDD** | `status` → statusHistory, `message` → content, `replace` → content (écrase), `embeds` → embeds, `files` → files, `source`/`citation` → sources | Survivent à la déconnexion |
| **Non persistés** | `chat:completion`, `chat:message:delta`, `chat:message:error`, `chat:message:follow_ups`, `chat:message:favorite`, `chat:title`, `chat:tags`, `notification` | Socket.IO uniquement, perdus à la déconnexion |
| **Requièrent connexion live** | `confirmation`, `input`, `execute` via `__event_call__` | Erreur si déconnecté, timeout 300s |

> **Important :** Utiliser les noms courts (`message`, `replace`, `files`, `status`, `source`) pour la persistance en BDD. Les noms longs (`chat:message:delta`, `chat:message:files`) fonctionnent côté frontend mais ne persistent pas.

## Matrice de compatibilité par type de fonction

| Capacité | Tools | Actions | Pipes | Filters |
|----------|-------|---------|-------|---------|
| `__event_emitter__` | ✅ | ✅ | ✅ | ✅ |
| `__event_call__` | ✅ | ✅ | ✅ | ✅ |
| Return value → réponse utilisateur | ✅ | ✅ | ✅ | ❌ |
| `HTMLResponse` → Rich UI embed | ✅ | ✅ | ❌ | ❌ |

## Exemples de code

### Status Event

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
await __event_emitter__({
    "type": "status",
    "data": {
        "description": "Done!",
        "done": True,
    },
})
```

### Confirmation (bidirectionnelle)

```python
result = await __event_call__({
    "type": "confirmation",
    "data": {
        "title": "Are you sure?",
        "message": "Do you really want to proceed?"
    }
})
if result:
    pass  # Utilisateur a confirmé
else:
    pass  # Utilisateur a annulé
```

### Input (bidirectionnel)

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

### Input password

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

### Execute JavaScript (bidirectionnel avec retour)

```python
result = await __event_call__({
    "type": "execute",
    "data": {
        "code": "return document.title;",
    }
})
```

### Execute JavaScript (fire-and-forget)

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

### Formulaire custom via execute

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

### Citation

```python
class Tools:
    def __init__(self):
        self.citation = False  # REQUIS pour utiliser des citations custom

    async def research_tool(self, topic: str, __event_emitter__=None) -> str:
        if not __event_emitter__:
            return "Research completed (citations not available)"

        sources = [
            {
                "title": "Advanced AI Systems",
                "url": "https://example.com/ai-systems",
                "content": "Artificial intelligence systems have evolved...",
                "author": "Dr. Jane Smith",
                "date": "2024-03-15"
            }
        ]

        for source in sources:
            await __event_emitter__({
                "type": "citation",
                "data": {
                    "document": [source["content"]],
                    "metadata": [{
                        "date_accessed": datetime.now().isoformat(),
                        "source": source["title"],
                        "author": source["author"],
                        "publication_date": source["date"],
                        "url": source["url"]
                    }],
                    "source": {
                        "name": source["title"],
                        "url": source["url"]
                    }
                }
            })

        return f"Research on '{topic}' completed. Found {len(sources)} sources."
```

> Les citations fonctionnent identiquement en mode Default et Native. Pour des citations distinctes, s'assurer que les identifiants de chaque citation sont différents (le mécanisme de groupement fusionne les citations de même ID — Issue #17366).

### Métadonnées de citation personnalisables

Le champ `metadata` des citations supporte des champs étendus selon le type de source :

```python
# Citation académique
await __event_emitter__({
    "type": "citation",
    "data": {
        "document": [source["content"]],
        "metadata": [{
            "date_accessed": datetime.now().isoformat(),
            "source": source["title"],
            "authors": source["authors"],
            "journal": source["journal"],
            "volume": source["volume"],
            "pages": source["pages"],
            "doi": source["doi"],
            "publication_date": source["date"],
            "type": "academic_journal"
        }],
        "source": {"name": f"{source['title']} - {source['journal']}", "url": f"https://doi.org/{source['doi']}"}
    }
})

# Enregistrement de base de données
await __event_emitter__({
    "type": "citation",
    "data": {
        "document": [record["data"]],
        "metadata": [{
            "date_accessed": datetime.now().isoformat(),
            "source": f"Database Table: {record['table']}",
            "record_id": record["record_id"],
            "last_updated": record["last_updated"],
            "type": "database_record"
        }],
        "source": {"name": f"Record {record['record_id']}", "url": f"db://{record['table']}/{record['record_id']}"}
    }
})
```

**Valeurs connues pour `type` :** `"academic_journal"`, `"database_record"`, `"web_page"`, etc.

## Événements pour outils externes

Les outils externes (OpenAPI/MCP) peuvent émettre des événements via un endpoint REST.

**Prérequis :** Variable d'environnement `ENABLE_FORWARD_USER_INFO_HEADERS=True`

**Headers fournis automatiquement :**
- `X-Open-WebUI-Chat-Id`
- `X-Open-WebUI-Message-Id` (noms configurables)

**Endpoint :** `POST /api/v1/chats/{chat_id}/messages/{message_id}/event` avec auth API key/session token

**Payload :**

```json
{
    "type": "status",
    "data": {
        "description": "Processing...",
        "done": false
    }
}
```

> Le payload suit la même structure que `__event_emitter__` : un objet avec `type` et `data`.

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/events — consultée le 13/04/2026

**Limitation :** Seuls les événements one-way (status, notification) sont disponibles pour les outils externes. Les événements interactifs (confirmation, input) nécessitent des outils Python natifs.
