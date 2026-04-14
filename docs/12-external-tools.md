# Outils externes (OpenAPI + MCP)

Open WebUI supporte deux types d'outils externes : les serveurs **OpenAPI** et les serveurs **MCP (Model Context Protocol)**. Ces outils s'exécutent en dehors du processus Open WebUI et sont accessibles au LLM via function calling.

> Pour la plupart des déploiements, **OpenAPI** reste le chemin d'intégration préféré.
>
> Source : https://docs.openwebui.com/features/extensibility/mcp.mdx + https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/index.mdx — consultée le 13/04/2026

## OpenAPI Tool Servers

### Pourquoi OpenAPI

- Standard établi, production-proven
- Pas de protocole propriétaire — si vous construisez des REST APIs, vous êtes déjà prêt
- Intégration facile et hébergement flexible
- Sécurité solide : HTTPS, OAuth, JWT, API Keys
- Écosystème d'outils riche (génération code, documentation, validation, mocking)
- Futur-proof et stable

### Limitations

- **Événements one-way uniquement** : les outils OpenAPI peuvent émettre des status updates et notifications via le REST endpoint, mais les événements interactifs (confirmation, input utilisateur) sont réservés aux outils Python natifs
- **Pas de streaming** : les réponses sont retournées en bloc, pas token par token
- CORS requis pour les serveurs locaux

> Source : https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/index.mdx — consultée le 13/04/2026

### Quickstart

```bash
git clone https://github.com/open-webui/openapi-servers
cd openapi-servers/servers/time
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --reload
```

Le serveur est accessible à `http://localhost:8000`. La documentation interactive à `http://localhost:8000/docs`.

### Connexion dans Open WebUI

1. Ouvrir **⚙️ Settings → ➕ Tools**
2. Entrer l'URL du serveur (ex: `http://localhost:8000`)
3. Cliquer "Save"

### CORS — Indispensable pour les serveurs locaux

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**HTTPS en production :** Si Open WebUI est servi en HTTPS, les serveurs locaux doivent aussi être en HTTPS, ou tourner sur localhost (127.0.0.1).

### operationId

Il est important de définir un `operationId` custom pour tous les endpoints.

### Configuration via variable d'environnement

`TOOL_SERVER_CONNECTIONS` : JSON array de configurations de connexion. Supporte les types `"openapi"` et `"mcp"`.

```json
[
  {
    "type": "openapi",
    "url": "http://example.com/api",
    "spec_type": "url",
    "spec": "",
    "path": "openapi.json",
    "auth_type": "bearer",
    "key": "your_api_key",
    "config": {"enable": true},
    "info": {
      "id": "server-1",
      "name": "Example OpenAPI Tool Server",
      "description": "Connects to an example OpenAPI tool."
    }
  },
  {
    "type": "mcp",
    "url": "http://localhost:3000/sse",
    "auth_type": "oauth_2.1",
    "key": "",
    "config": {"enable": true},
    "info": {
      "id": "server-2",
      "name": "Example MCP Server",
      "description": "Connects to an example MCP server."
    }
  }
]
```

> **Stabilité MCP :** Le support MCP est en amélioration continue. L'écosystème plus large est encore en évolution — attendez-vous à des breaking changes occasionnels.

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers/open-webui.mdx — consultée le 13/04/2026

### N'importe quel framework/langage

FastAPI, Flask+Flask-RESTX, Express+Swagger, Spring Boot, Go avec Swag... La seule exigence est une spec OpenAPI valide avec des operationId.

### Types d'outils possibles

- Opérations filesystem (read/write, list directories)
- Accès Git et repositories
- Requêtes base de données
- Web scrapers / summarizers
- Intégrations SaaS (Salesforce, Jira, Slack)
- Composants mémoire / RAG
- Microservices internes sécurisés

---

## MCP (Model Context Protocol)

Disponible nativement depuis **v0.6.31**. Supporte le transport **Streamable HTTP uniquement** (pas stdio, pas SSE natif).

> Open WebUI est un environnement web multi-tenant, pas un processus desktop local. Les connexions stdio/SSE longue durée sont incompatibles avec cette architecture.

### Prérequis : WEBUI_SECRET_KEY

Vous **DEVEZ** définir `WEBUI_SECRET_KEY` dans votre Docker config. Sans elle, les outils OAuth MCP casseront à chaque redémarrage (Error: `Error decrypting tokens`).

### Configuration

1. Ouvrir **⚙️ Admin Settings → External Tools**
2. Cliquer **+ (Add Server)**
3. Définir **Type** sur **MCP (Streamable HTTP)**
4. Entrer l'**URL du serveur** et les détails **Auth**
5. **Save**

### Erreur courante : mauvais type de connexion

Si vous ajoutez un serveur MCP en sélectionnant le type **OpenAPI**, l'UI va crasher ou afficher un écran de chargement infini.

**Solution :**
1. Désactiver la connexion problématique via Admin Settings
2. Rafraîchir (Ctrl+F5)
3. Ré-ajouter avec le bon Type **MCP (Streamable HTTP)**

### Modes d'authentification

| Mode | Quand l'utiliser |
|------|-----------------|
| **None** | Serveurs locaux ou réseau interne sans token. **À utiliser par défaut** sauf si le serveur requiert explicitement un token. |
| **Bearer** | Uniquement si le serveur requiert un token API spécifique. **Le champ Key est obligatoire.** |
| **OAuth 2.1** | Dynamic Client Registration (DCR). Quand le serveur supporte l'enregistrement automatique de clients OAuth. |
| **OAuth 2.1 (Static)** | Quand vous avez déjà un client ID/secret pré-créé par votre IdP. |

**Attention Bearer :** Sélectionner "Bearer" sans fournir de key envoie un header `Authorization: Bearer` vide, ce qui provoque un rejet immédiat par beaucoup de serveurs.

### OAuth 2.1 (Static) Setup

1. Sélectionner **OAuth 2.1 (Static)** dans Auth
2. Entrer **Client ID** et **Client Secret**
3. Cliquer **Register Client**
4. **Save**
5. Ouvrir un chat → **+ → Integrations → Tools** → activer l'outil MCP
6. Compléter le flow OAuth dans le navigateur

### Limitation OAuth 2.1 : pas de default tools

**Ne pas définir d'outils OAuth 2.1 MCP comme default/pre-enabled sur un modèle.** Le flow OAuth nécessite une redirection navigateur interactive qui ne peut pas se produire pendant une requête chat completion.

**Workaround :** Les utilisateurs activent manuellement les outils OAuth 2.1 par chat via le bouton **➕** dans la zone d'input.

### URLs de connexion en Docker

Si Open WebUI tourne en Docker et le serveur MCP est sur la machine hôte :
- Utiliser `http://host.docker.internal:<port>` (ex: `http://host.docker.internal:3000/sse`) au lieu de `localhost`

### Function Name Filter List

Restreint quels outils sont exposés au LLM. Laisser vide pour exposer tous les outils.

**Workaround bug :** Si erreur de connexion avec une liste vide, ajouter une simple virgule (`,`) pour forcer le système à traiter le champ comme un filtre valide.

---

## MCPO — Proxy MCP vers OpenAPI

Pour les serveurs MCP qui utilisent **stdio** ou **SSE** (non Streamable HTTP), le proxy [mcpo](https://github.com/open-webui/mcpo) traduit les transports en endpoints OpenAPI compatibles.

### Quickstart

```bash
uvx mcpo --port 8000 -- uvx mcp-server-time --local-timezone=America/New_York
```

Le serveur est accessible à `http://localhost:8000` avec documentation interactive à `http://localhost:8000/docs`.

### Dockerfile pour production

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install mcpo uv
CMD ["uvx", "mcpo", "--host", "0.0.0.0", "--port", "8000", "--", "uvx", "mcp-server-time", "--local-timezone=America/New_York"]
```

> Le flag `--host 0.0.0.0` est requis dans les conteneurs Docker pour exposer le service sur toutes les interfaces réseau.

### Fonctionnement

- Au démarrage, le proxy se connecte au serveur MCP pour découvrir les outils
- Il construit automatiquement des endpoints FastAPI basés sur les schémas MCP
- Documentation Swagger UI auto-générée
- Asynchrone et performant

### Événements supportés

Les outils exposés via mcpo peuvent émettre des événements (status, notifications) via l'endpoint REST d'Open WebUI. Les headers `X-Open-WebUI-Chat-Id` et `X-Open-WebUI-Message-Id` sont passés automatiquement.

> Source : https://github.com/open-webui/docs/blob/main/docs/features/extensibility/plugin/tools/openapi-servers/mcp.mdx — consultée le 13/04/2026

---

## MCP vs OpenAPI : quand choisir quoi

| Critère | OpenAPI | MCP |
|---------|---------|-----|
| Prêt pour la production | ✅ Standard mature | ⚠️ En évolution |
| SSO / API gateways | ✅ Natif | ❌ Limité |
| Observabilité | ✅ Tracing, audit | ⚠️ Basique |
| Protocole streaming | ❌ Réponse complète | ✅ Streamable HTTP |
| Écosystème outils | ✅ Massive | 🔄 En croissance |
| Setup complexité | Faible (REST standard) | Moyenne (nouveau protocole) |
| Multi-tenant web | ✅ Conçu pour | ⚠️ Limites CORS/CSRF |

> Vous n'avez pas à choisir : beaucoup d'équipes exposent OpenAPI en interne et wrappe MCP au bord pour des clients spécifiques.
