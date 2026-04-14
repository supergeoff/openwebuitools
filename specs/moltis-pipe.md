# Moltis GraphQL API → OpenAI API Mapping

Ce document décrit comment créer un **pipe** (middleware) qui expose l'API Moltis via GraphQL sous forme d'une API **OpenAI-compatible** pour permettre à OpenWebUI de s'y connecter.

---

## 1. Vue d'ensemble

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────┐     ┌─────────────┐
│  OpenWebUI  │────▶│  Pipe (middleware)│────▶│  Moltis       │────▶│  OpenRouter │
│  (client)   │◀────│  GraphQL        │◀────│  GraphQL API  │◀────│  (LLM)      │
└─────────────┘     └──────────────────┘     └───────────────┘     └─────────────┘
```

**Port par défaut:** `36531`  
**Protocole:** GraphQL (HTTP + WebSocket pour subscriptions)  
**GraphQL endpoint:** `https://<host>:36531/graphql`

---

## 2. Schema GraphQL Moltis

### 2.1 Root Types

```graphql
type QueryRoot {
  # Status
  health: HealthInfo!
  status: StatusInfo!
  
  # Chat
  chat: ChatQuery!
  
  # Sessions
  sessions: SessionQuery!
  
  # Channels
  channels: ChannelQuery!
  
  # Nodes, System, Device...
  system: SystemQuery!
  node: NodeQuery!
}

type MutationRoot {
  system: SystemMutation!
  node: NodeMutation!
  device: DeviceMutation!
  chat: ChatMutation!
}

type SubscriptionRoot {
  chatEvent(sessionKey: String): GenericEvent!
}
```

---

## 3. Types Principaux

### 3.1 ChatMutation (Envoyer des messages)

```graphql
type ChatMutation {
  # Envoyer un message et recevoir une confirmation
  send(
    message: String!
    sessionKey: String
    model: String
  ): BoolResult!
  
  # Aborter une réponse en cours
  abort(sessionKey: String): BoolResult!
  
  # Annuler les messages en file d'attente
  cancelQueued(sessionKey: String): BoolResult!
  
  # Effacer l'historique de chat
  clear(sessionKey: String): BoolResult!
  
  # Compacter les messages (résumé contextuel)
  compact(sessionKey: String): BoolResult!
  
  # Injecter un message dans l'historique
  inject(input: JSON!): BoolResult!
}
```

**Exemple d'appel:**
```graphql
mutation {
  chat.send(message: "Hello world!", sessionKey: "openwebui:user123") {
    ok
  }
}
```

### 3.2 ChatQuery (Lire l'historique)

```graphql
type ChatQuery {
  # Obtenir l'historique de chat (format brut)
  history(sessionKey: String): JSON!
  
  # Obtenir les données de contexte
  context(sessionKey: String): JSON!
  
  # Obtenir le prompt système rendu
  rawPrompt(sessionKey: String): ChatRawPrompt!
  
  # Obtenir le contexte complet (format OpenAI messages)
  fullContext(sessionKey: String): JSON!
}
```

**Exemple d'appel:**
```graphql
query {
  chat.fullContext(sessionKey: "openwebui:user123") {
    messages {
      role
      content
    }
    messageCount
  }
}
```

### 3.3 SessionQuery (Gérer les sessions)

```graphql
type SessionQuery {
  # Lister toutes les sessions
  list: [SessionEntry!]!
  
  # Aperçu d'une session sans switcher
  preview(key: String!): SessionEntry!
  
  # Rechercher des sessions par query
  search(query: String!): [SessionEntry!]!
  
  # Résoudre ou créer une session
  resolve(key: String!): SessionEntry!
  
  # Obtenir les branches d'une session
  branches(key: String): [SessionBranch!]!
  
  # Lister les partages de session
  shares(key: String): [SessionShareResult!]!
  
  # Vérifier si la session a un run actif
  active(sessionKey: String!): SessionActiveResult!
}
```

### 3.4 GenericEvent (Events de streaming)

```graphql
type GenericEvent {
  data: JSON!
}
```

**Structure du JSON selon `state`:**

#### Event de streaming (`state: "delta"`):
```json
{
  "runId": "75e008e4-da94-4d15-becf-9d56c5faf525",
  "seq": null,
  "sessionKey": "test-openwebui",
  "state": "delta",
  "text": " de"
}
```

**Signification:**
- `runId`: UUID unique du run LLM
- `sessionKey`: Clé de session (ex: `telegram:moltisforgeoff_bot:6915143689`)
- `state`: Type d'event (`"delta"` = token en streaming)
- `text`: Token reçu (peut être un mot, caractère, ou fragment)

#### Event final (`state: "final"`):
```json
{
  "cacheReadTokens": 30624,
  "cacheWriteTokens": 0,
  "durationMs": 1810,
  "inputTokens": 30707,
  "iterations": 1,
  "messageIndex": 5,
  "model": "openrouter::z-ai/glm-5.1",
  "outputTokens": 26,
  "provider": "openrouter",
  "replyMedium": "text",
  "requestCacheReadTokens": 30624,
  "requestCacheWriteTokens": 0,
  "requestInputTokens": 30707,
  "requestOutputTokens": 26,
  "runId": "65464059-16af-43aa-8079-de1ab9dd09fc",
  "sessionKey": "test-openwebui",
  "state": "final",
  "text": "Three for three! 🐼 All good on my end.",
  "toolCallsMade": 0
}
```

**Signification:**
- `state`: `"final"` = réponse complète terminée
- `text`: Texte complet de la réponse
- `model`: Modèle utilisé (ex: `openrouter::z-ai/glm-5.1`)
- `outputTokens`: Nombre de tokens générés
- `inputTokens`: Nombre de tokens en entrée
- `durationMs`: Temps de génération en millisecondes
- `replyMedium`: Type de réponse (`"text"`, `"voice"`, etc.)
- `toolCallsMade`: Nombre d'outils appellés

#### Event d'erreur (`state: "error"`):
À déterminer — non testé encore.

### 3.5 BoolResult

```graphql
type BoolResult {
  ok: Boolean!
}
```

**Exemple de réponse:**
```json
{
  "data": {
    "chatSend": {
      "ok": true
    }
  }
}
```

### 3.6 fullContext (Format OpenAI messages)

**Query:**
```graphql
query {
  chat.fullContext(sessionKey: "test-openwebui")
}
```

**Réponse:**
```json
{
  "llmOutputs": [
    {
      "cacheReadTokens": 31232,
      "cacheWriteTokens": 0,
      "content": "Contenu de la réponse LLM...",
      "created_at": 1776195200489,
      "durationMs": 17997,
      "inputTokens": 31737,
      "llmApiResponse": [
        {
          "choices": [
            {
              "delta": {
                "content": "ars",
                "role": "assistant"
              },
              "finish_reason": null,
              "index": 0
            }
          ],
          "created": 1776195182,
          "id": "gen-1776195182-wS6vDfkOALE6JictHt54",
          "model": "z-ai/glm-5.1-20260406",
          "object": "chat.completion.chunk",
          "provider": "Z.AI"
        }
      ],
      "model": "openrouter::z-ai/glm-5.1",
      "outputTokens": 528,
      "provider": "openrouter",
      "reasoning": "...",
      "role": "assistant",
      "run_id": "75e008e4-da94-4d15-becf-9d56c5faf525"
    }
  ],
  "messages": [
    {
      "content": "You are a helpful assistant...",
      "role": "system"
    },
    {
      "content": "Hello test",
      "role": "user"
    },
    {
      "content": "Hello! 👋 Just a test run...",
      "role": "assistant"
    }
  ],
  "messageCount": 15,
  "promptMemory": {
    "chars": 1488,
    "fileSource": "agent_workspace",
    "mode": "live-reload",
    "path": "/data/agents/main/MEMORY.md",
    "present": true,
    "snapshotActive": false,
    "style": "hybrid",
    "writeMode": "hybrid"
  },
  "systemPromptChars": 28392,
  "totalChars": 34817,
  "truncated": false,
  "workspaceFiles": []
}
```

**Note:** `messages` est un array au format OpenAI standard:
```json
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]
```

---

## 4. Mapping OpenAI API → Moltis GraphQL

### 4.1 Endpoint OpenAI

Le pipe doit exposer:
```
POST /v1/chat/completions
GET  /v1/models
```

---

### 4.2 POST /v1/chat/completions

**Format OpenAI input:**
```json
{
  "model": "moltis",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**Mapping vers Moltis:**

#### Étape 1: Envoyer le message (Mutation)

```graphql
mutation SendMessage($message: String!, $sessionKey: String) {
  chat.send(message: $message, sessionKey: $sessionKey) {
    ok
  }
}
```

**Variables:**
```json
{
  "message": "Hello!",
  "sessionKey": "openwebui:user123"
}
```

**Note:** Pour construire le message complet à envoyer:
1. Récupérer `chat.fullContext(sessionKey: "openwebui:user123")` pour avoir l'historique
2. Prendre les `messages` non-system (ou reconstruire le prompt)
3. Concaténer les derniers messages pour former le contexte
4. Envoyer le dernier message utilisateur via `chat.send`

#### Étape 2: Streamer les tokens (Subscription)

```graphql
subscription OnChatEvent($sessionKey: String) {
  chatEvent(sessionKey: $sessionKey) {
    data
  }
}
```

**Variables:**
```json
{
  "sessionKey": "openwebui:user123"
}
```

**Mapping des events vers SSE OpenAI:**

Pour `state: "delta"`:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion.chunk",
  "created": 1234567890,
  "model": "moltis",
  "choices": [{
    "index": 0,
    "delta": {
      "content": "<text>"
    },
    "finish_reason": null
  }]
}
```

Pour `state: "final"` (dernier event):
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "moltis",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "<full text>"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

**Format SSE:** `data: {...}\n\n`

---

### 4.3 GET /v1/models

**Réponse OpenAI:**
```json
{
  "object": "list",
  "data": [
    {
      "id": "moltis",
      "object": "model",
      "created": 1234567890,
      "owned_by": "moltis"
    }
  ]
}
```

**Mapping:** Retourner une liste固定 de modèles Moltis (Hardcodé dans le pipe):

```json
{
  "object": "list",
  "data": [
    {
      "id": "moltis",
      "object": "model",
      "created": 1700000000,
      "owned_by": "moltis"
    }
  ]
}
```

---

### 4.4 Non-streaming /chat/completions

Si `stream: false`:

1. Envoyer le message via `chat.send`
2. Attendre l'event `state: "final"`
3. Retourner le JSON complet:

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "moltis",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "<full text from final event>"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": <inputTokens from final event>,
    "completion_tokens": <outputTokens from final event>,
    "total_tokens": <inputTokens + outputTokens>
  }
}
```

---

## 5. Gestion des Sessions

### 5.1 Créer/Résoudre une session

```graphql
query {
  sessions.resolve(key: "openwebui:user123") {
    key
    label
    createdAt
  }
}
```

**Note:** Si la session n'existe pas, Moltis la crée automatiquement lors du premier `chat.send`.

### 5.2 Clé de session

**Format recommandé:** `openwebui:<user_id>`  
**Exemple:** `openwebui:user_abc123`

**Contraintes:**
- Doit être une chaîne non-null
- Utilisé pour corréler les messages d'un même utilisateur
- Moltis crée la session à la volée si elle n'existe pas

---

## 6. Gestion du Contexte (Historique)

### 6.1 Récupérer le contexte complet

```graphql
query GetContext($sessionKey: String!) {
  chat.fullContext(sessionKey: $sessionKey) {
    messages {
      role
      content
    }
    messageCount
    totalChars
  }
}
```

### 6.2 Format des messages

Le champ `messages` dans `fullContext` contient:

```json
[
  {"role": "system", "content": "You are a helpful assistant..."},
  {"role": "user", "content": "Hello!"},
  {"role": "assistant", "content": "Hi there!"}
]
```

**Mapping vers OpenAI:** Direct — le format est identique.

### 6.3 Construire le prompt à envoyer

Pour envoyer un nouveau message:
1. Appeler `chat.fullContext` pour récupérer l'historique
2. Le dernier message du array `messages` est le plus récent
3. L'envoyer via `chat.send(message: <last_user_message>, sessionKey: ...)`

**Note:** Moltis gère automatiquement le contexte système et le prompt memory.

---

## 7. Erreurs et Cas Limites

### 7.1 Chat.send retourne `ok: false`

```json
{
  "data": {
    "chatSend": {
      "ok": false
    }
  }
}
```

**Action:** Retourner une erreur HTTP 500 avec le message approprié.

### 7.2 Session non trouvée

Moltis crée automatiquement la session si elle n'existe pas lors de `chat.send`.

### 7.3 Connection perdue pendant le streaming

Le pipe doit:
1. Timeout le stream après un délai raisonable (ex: 60s)
2. Retourner un event de fin avec `finish_reason: "length"` si le timeout est atteint

### 7.4 Abort (annulation)

```graphql
mutation {
  chat.abort(sessionKey: "openwebui:user123") {
    ok
  }
}
```

**Note:** OpenWebUI n'envoie pas d'abort, mais le pipe peut l'implémenter si nécessaire.

---

## 8. Exemple de Code Pipe (Pseudo-code)

```python
# Pipe Moltis → OpenAI pour OpenWebUI

MOLTIS_GRAPHQL = "https://<host>:36531/graphql"
SESSION_PREFIX = "openwebui"

class MoltisPipe:
    def __init__(self, host: str):
        self.graphql_url = f"https://{host}/graphql"
        self.ws_url = f"wss://{host}/graphql"  # WebSocket for subscriptions
    
    async def chat_completions(self, request: dict) -> SSEStream:
        messages = request["messages"]
        session_key = f"{SESSION_PREFIX}:{request.get('user_id', 'anonymous')}"
        stream = request.get("stream", True)
        
        # Get last user message
        last_msg = messages[-1]["content"] if messages else ""
        
        # Send message via GraphQL mutation
        mutation = """
        mutation SendMessage($message: String!, $sessionKey: String) {
          chat.send(message: $message, sessionKey: $sessionKey) {
            ok
          }
        }
        """
        await self.gql_mutate(mutation, {"message": last_msg, "sessionKey": session_key})
        
        # Subscribe to chat events
        subscription = """
        subscription OnChatEvent($sessionKey: String) {
          chatEvent(sessionKey: $sessionKey) {
            data
          }
        }
        """
        
        if stream:
            return self._stream_events(subscription, session_key)
        else:
            return await self._wait_final(subscription, session_key)
    
    async def _stream_events(self, subscription: str, session_key: str):
        async for event in self.gql_subscribe(subscription, {"sessionKey": session_key}):
            data = event["data"]["chatEvent"]["data"]
            state = data.get("state")
            
            if state == "delta":
                yield f"data: {json.dumps(self._delta_to_openai(data))}\n\n"
            elif state == "final":
                yield f"data: {json.dumps(self._final_to_openai(data))}\n\n"
                yield "data: [DONE]\n\n"
    
    def _delta_to_openai(self, data: dict) -> dict:
        return {
            "id": "chatcmpl-" + data.get("runId", "")[:8],
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "moltis",
            "choices": [{
                "index": 0,
                "delta": {"content": data.get("text", "")},
                "finish_reason": None
            }]
        }
    
    def _final_to_openai(self, data: dict) -> dict:
        return {
            "id": "chatcmpl-" + data.get("runId", "")[:8],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "moltis",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": data.get("text", "")},
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": data.get("inputTokens", 0),
                "completion_tokens": data.get("outputTokens", 0),
                "total_tokens": (data.get("inputTokens", 0) + data.get("outputTokens", 0))
            }
        }
    
    async def list_models(self) -> dict:
        return {
            "object": "list",
            "data": [{
                "id": "moltis",
                "object": "model",
                "created": 1700000000,
                "owned_by": "moltis"
            }]
        }
```

---

## 9. Notes d'implémentation

### 9.1 Authentification

Le pipe doit gérer l'authentification Moltis. Options:
- **Header `Authorization: Bearer <token>`** propagé vers Moltis
- **Session cookies** si le pipe fait tourner un navigateur headless
- **API key dans le header** si Moltis supporte l'auth par clé

### 9.2 WebSocket / Subscriptions

GraphQL subscriptions nécessitent WebSocket. Libraries recommandées:
- **Python:** `graphql-transport-ws` ou `strawberry-graphql`
- **Node.js:** `graphql-ws` ou `subscriptions-transport-ws`

### 9.3 TLS

Moltis utilise TLS par défaut (`enabled = true`). Le pipe doit:
- Soit faire confiance au certificat auto-généré
- Soit configurer `MOLTIS_TLS_TRUST_ANY=true` dans le pipe

### 9.4 Rate Limiting

Pas de rate limiting détecté dans l'API GraphQL. À surveiller si OpenWebUI fait beaucoup de requêtes.

---

## 10. Endpoints à Exposer

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/v1/chat/completions` | Chat principal (streaming ou non) |
| `GET` | `/v1/models` | Liste des modèles disponibles |
| `GET` | `/health` | Santé du pipe |

---

## 11. Ressources

- **GraphQL Playground:** `https://<host>:36531/graphql`
- **Doc Explorer:** Disponible dans le playground (Ctrl+K)
- **Logs Moltis:** `/data/logs.jsonl` (contient les traces GraphQL)

---

*Document généré le 2025-04-14 à partir de l'exploration de l'API Moltis v2.*