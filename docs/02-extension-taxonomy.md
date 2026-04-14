# Taxonomie du système d'extensibilité Open WebUI

## Trois couches d'extensibilité

Open WebUI offre trois couches distinctes pour étendre ses capacités :

| Couche | Mécanisme | Exécution | Cas d'usage |
|--------|-----------|-----------|-------------|
| **1. In-process Python** | Tools & Functions | Dans le processus Open WebUI | Logique custom, interaction UI, filtrage |
| **2. External HTTP** | OpenAPI & MCP servers | Services externes | Intégrations SaaS, APIs tierces, outils hébergés |
| **3. Pipeline workers** | Pipelines | Conteneur Docker séparé (port 9099) | Tâches lourdes, packages custom, isolation |

> Source : https://docs.openwebui.com/features/extensibility/pipelines/ — consultée le 13/04/2026

## Types d'extensions principaux

### Tools (outils appelés par le LLM)

Scripts Python exécutés dans l'environnement Open WebUI, appelés par le LLM via function calling. Définition officielle : *"Python scripts that run directly within the Open WebUI environment"*. Deux modes de tool calling : **Default** (Legacy, injection dans le prompt) et **Native** (Agentic, capacités natives du modèle).

Gérés dans les onglets **Workspace**. Capacités complètes de Python.

> "Workspace Tools execute arbitrary Python code on your server. Only install from trusted sources, review code before importing, and restrict Workspace access to trusted administrators only. Granting a user the ability to create or import Tools is equivalent to giving them shell access."
>
> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consultée le 13/04/2026

### Functions (trois sous-types)

Gérées depuis l'**Admin Panel**. Aident "the WebUI itself do more things, like adding new AI models". Exécution via `exec` dans le processus Open WebUI.

#### Pipe Function (modèle/agent custom)

Se présente comme un **modèle autonome** dans l'interface. Traite les requêtes avec logique custom. Peut exposer plusieurs modèles via le pattern Manifold (`pipes()` retournant une liste).

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/ — consultée le 13/04/2026

#### Filter Function (pré/post-traitement)

Modifie les données en entrée (`inlet`), en streaming (`stream`) et en sortie (`outlet`) du LLM. Agit comme middleware.

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ — consultée le 13/04/2026

#### Action Function (boutons interactifs)

Boutons interactifs dans la barre de messages, exécute du Python côté serveur. Communication bidirectionnelle avec l'utilisateur via `__event_call__`.

> Source : https://docs.openwebui.com/features/extensibility/plugin/functions/action/ — consultée le 13/04/2026

### Pipelines (service séparé)

Service séparé déployé via Docker (`ghcr.io/open-webui/pipelines:main`), port 9099. **Python 3.11 requis.** Recommandé quand "dealing with computationally heavy tasks that you want to offload from your main Open WebUI instance for better performance and scalability." Compatible avec tout client supportant l'API OpenAI.

> Source : https://docs.openwebui.com/features/extensibility/pipelines/ — consultée le 13/04/2026

### Outils externes (OpenAPI & MCP)

- **OpenAPI Tool Servers** : services REST externes exposant une spec OpenAPI. Intégration via Admin Settings → External Tools.
- **MCP (Model Context Protocol)** : protocole standard supporté nativement depuis v0.6.31. Connexion Streamable HTTP uniquement.

> Voir [12-external-tools.md](12-external-tools.md) pour les détails complets.

## Tableau comparatif

| Aspect | Tools | Pipe | Filter | Action | Pipeline | OpenAPI | MCP |
|--------|-------|------|--------|--------|----------|---------|-----|
| **Qui appelle** | Le LLM (function calling) | L'utilisateur (sélection modèle) | Automatique (middleware) | L'utilisateur (clic bouton) | L'utilisateur (sélection modèle) | Le LLM (function calling) | Le LLM (function calling) |
| **Où ça tourne** | Processus Open WebUI | Processus Open WebUI | Processus Open WebUI | Processus Open WebUI | Conteneur Docker séparé | Service externe | Service externe |
| **UI** | Workspace | Admin Panel (modèle) | Admin Panel (filter) | Boutons sous messages | Admin Panel (modèle) | External Tools | External Tools |
| **Import packages** | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | Via frontmatter `requirements` (pip install runtime) | N'importe quel package | N/A (service externe) | N/A (service externe) |
| **Events** | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | `__event_emitter__` + `__event_call__` | Via REST endpoint | One-way (REST endpoint) | One-way (REST endpoint) |
| **Rich UI** | HTMLResponse | Non | Non | HTMLResponse | Non | Non | Non |
| **Valves** | Oui | Oui | Oui | Oui | Oui | N/A | N/A |

## Functions internes vs Pipelines externes

| Aspect | Functions internes | Pipelines externes |
|--------|-------------------|-------------------|
| Exécution | Dans le processus Open WebUI | Conteneur Docker dédié (port 9099) |
| Import packages | Via frontmatter `requirements` (mécanisme runtime pip install, pas un vrai import Python natif) | N'importe quel package Python |
| Isolation | Aucune (même processus) | Isolé dans son propre conteneur |
| Configuration | Admin Panel | Admin Panel > Settings > Connections |
| Connexion | N/A | URL: `http://localhost:9099`, API key: `0p3n-w3bu!` |
| Déploiement | Intégré | `docker run -d -p 9099:9099 --add-host=host.docker.internal:host-gateway -v pipelines:/app/pipelines --name pipelines --restart always ghcr.io/open-webui/pipelines:main` |
| Chargement auto | N/A | Tous les pipelines dans `/pipelines` sont chargés au démarrage. Configurable via `PIPELINES_DIR` |

> "If your goal is simply to add support for additional providers...you likely don't need Pipelines." Utiliser les Functions internes pour les cas basiques.
>
> Source : https://docs.openwebui.com/features/extensibility/pipelines/ — consultée le 13/04/2026

## Confusion nomenclature connue

La communauté a identifié une confusion significative dans la taxonomie (Discussion GitHub #16415) :

- 5 catégories distinctes créent la confusion : **Capabilities**, **Tools**, **Tool Servers**, **Functions** (Filters/Actions/Pipes), **Pipelines**
- "Tools" et "Capabilities" font des choses similaires avec des termes différents
- La structure de la documentation ne correspond pas à l'organisation de l'UI (ex : la doc met "Filters" et "Pipes" sous "Pipelines", mais l'UI les place sous "Functions")
- "Functions" combine 3 opérations avec des workflows utilisateur fondamentalement différents

**Solution proposée par la communauté :** Fusionner "capabilities", "tools" et "tool servers" sous "tools" unifié avec sous-catégories. Désagréger "Functions" en catégories nommées distinctes.

> Source : https://github.com/open-webui/open-webui/discussions/16415 — consultée le 13/04/2026
