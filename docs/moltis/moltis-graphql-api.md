# Documentation de l'API GraphQL Moltis

Ce document décrit l'API GraphQL exposée par Moltis.

## 1. Vue d'ensemble

**Protocole:** GraphQL (HTTP + WebSocket pour subscriptions)  
**GraphQL endpoint:** `https://<host>:<port>/graphql` (ex: `https://<host>:36531/graphql`)

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
      "model": "openrouter::z-ai/glm-5.1",
      "outputTokens": 528,
      "provider": "openrouter",
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

## 4. Gestion des Sessions

### 4.1 Créer/Résoudre une session

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

### 4.2 Clé de session

**Format recommandé (exemple OpenWebUI):** `openwebui:<user_id>`  
**Exemple:** `openwebui:user_abc123`

**Contraintes:**
- Doit être une chaîne non-null
- Utilisé pour corréler les messages d'un même utilisateur
- Moltis crée la session à la volée si elle n'existe pas

## 5. Gestion du Contexte (Historique)

### 5.1 Récupérer le contexte complet

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

### 5.2 Format des messages

Le champ `messages` dans `fullContext` contient:

```json
[
  {"role": "system", "content": "You are a helpful assistant..."},
  {"role": "user", "content": "Hello!"},
  {"role": "assistant", "content": "Hi there!"}
]
```

### 5.3 Construire un nouveau message

Pour envoyer un nouveau message:
1. Appeler `chat.fullContext` pour récupérer l'historique
2. Le dernier message du array `messages` est le plus récent
3. L'envoyer via `chat.send(message: <last_user_message>, sessionKey: ...)`

**Note:** Moltis gère automatiquement le contexte système et le prompt memory.

## 6. Erreurs et Cas Limites

### 6.1 Chat.send retourne `ok: false`

```json
{
  "data": {
    "chatSend": {
      "ok": false
    }
  }
}
```

### 6.2 Session non trouvée

Moltis crée automatiquement la session si elle n'existe pas lors de `chat.send`.

### 6.3 Abort (annulation)

```graphql
mutation {
  chat.abort(sessionKey: "openwebui:user123") {
    ok
  }
}
```

## 7. Ressources

- **GraphQL Playground:** `https://<host>:<port>/graphql`
- **Doc Explorer:** Disponible dans le playground (Ctrl+K)
- **Logs Moltis:** `/data/logs.jsonl` (contient les traces GraphQL)
