# Créer un Tool (outil appelé par le LLM)

Un Tool est un script Python exécuté dans l'environnement Open WebUI, appelé par le LLM via function calling. Le LLM décide quand et comment appeler les méthodes de votre Tool en fonction de leurs descriptions (docstrings) et de leurs signatures.

## Structure de base

```python
"""
title: String Inverse
author: Your Name
author_url: https://website.com
git_url: https://github.com/username/string-reverse.git
description: This tool calculates the inverse of a string
required_open_webui_version: 0.4.0
requirements: langchain-openai, langgraph, ollama
version: 0.4.0
licence: MIT
"""

from pydantic import BaseModel, Field

class Tools:
    def __init__(self):
        self.valves = self.Valves()
    
    class Valves(BaseModel):
        api_key: str = Field("", description="Your API key here")
    
    class UserValves(BaseModel):
        preference: str = Field("default", description="User preference")
    
    async def reverse_string(self, string: str) -> str:
        """
        Reverses the input string.
        :param string: The string to reverse
        """
        return string[::-1]
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consultée le 13/04/2026

## Exigences critiques

### Type hints obligatoires

Chaque argument de méthode **doit** avoir un type hint. Le système utilise les type hints pour générer le JSON schema transmis au LLM.

**Seuls 4 types primitifs sont supportés par le schema builder :** `str`, `int`, `float`, `bool`.

Tout type complexe (`Optional[str]`, `Dict[str, Any]`, `Union[int, str]`, `List[...]`) provoque des erreurs silencieuses ou `KeyError: 'type'`.

> Source : Discussion GitHub #13174 — consultée le 13/04/2026

### Docstrings obligatoires

"Without a docstring the calling LLM doesn't know what the function is for." Les docstrings doivent décrire chaque paramètre avec la syntaxe `:param name: description`.

**Docstrings ou type hints manquants = "list index out of range" errors.**

> Source : Discussion GitHub #3134 — consultée le 13/04/2026

### Méthodes async recommandées

Les méthodes async sont recommandées pour la compatibilité future et les opérations réseau.

## Frontmatter (metadata en docstring)

Le bloc triple-quote en tête de fichier définit les métadonnées du Tool :

| Champ | Description |
|-------|-------------|
| `title` | Nom affiché dans l'UI |
| `author` | Créateur |
| `author_url` | Lien optionnel vers le profil |
| `git_url` | Lien optionnel vers le repo source |
| `description` | Description brève |
| `required_open_webui_version` | Version minimum requise |
| `requirements` | Packages pip séparés par des virgules |
| `version` | Version de l'outil |
| `licence` | Licence de distribution |

## Gestion des packages externes

### Installation automatique via frontmatter

```python
"""
requirements: langchain-openai>=0.1.0,requests,beautifulsoup4
"""
```

Le système installe automatiquement les packages listés dans `requirements:` via pip.

**ATTENTION :** "When multiple tools define different versions of the same package... Open WebUI installs them in a non-deterministic order."

### Production : désactiver le pip install runtime

La variable `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS` (défaut: `True`) contrôle l'installation automatique.

**En production, il est fortement recommandé de la désactiver :**

```bash
ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False
```

Raisons :
- Empêche l'installation arbitraire de packages par des outils tiers
- Élimine les race conditions quand `UVICORN_WORKERS > 1` ou replicas multiples
- Assure des déploiements reproductibles

**Alternative :** pré-installer les packages via Dockerfile :

```dockerfile
FROM ghcr.io/open-webui/open-webui:main
RUN pip install --no-cache-dir python-docx requests beautifulsoup4
```

### Options pip supplémentaires

La variable d'environnement `PIP_OPTIONS` permet de contrôler le comportement de pip install :

```bash
PIP_OPTIONS="--upgrade --no-cache-dir"
```

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/development/ + Context7 — consultée le 13/04/2026

## Modes de Tool Calling

### Default Mode (Legacy)

- Injection dans le prompt
- Compatibilité universelle
- "Breaks KV cache" entre les tours
- Ne supporte pas les system tools

### Native Mode (Agentic)

- Utilise la capacité native de function-calling du modèle
- Définitions structurées, multi-step
- Requiert modèles frontier (GPT-5, Claude 4.5 Sonnet, Gemini 3 Flash, MiniMax M2.5)
- **INCOMPATIBILITÉ CRITIQUE :** "Message events (message, chat:message, chat:message:delta, replace) are BROKEN in Native mode because the server emits repeated content snapshots that overwrite tool-emitted updates."

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/ — consultée le 13/04/2026

### Compatibilité événements par mode

| Type d'événement | Default Mode | Native Mode | Statut |
|------------------|-------------|-------------|--------|
| status | ✅ Complet | ✅ Identique | Compatible |
| message | ✅ Complet | ❌ Cassé | Incompatible |
| citation | ✅ Complet | ✅ Identique | Compatible |
| notification | ✅ Complet | ✅ Identique | Compatible |
| files | ✅ Complet | ✅ Identique | Compatible |
| replace | ✅ Complet | ❌ Cassé | Incompatible |
| chat:message:delta | ✅ Complet | ❌ Cassé | Incompatible |

### Pattern de détection du mode

```python
async def adaptive_tool(self, __event_emitter__=None, __metadata__=None) -> str:
    mode = "default"
    if __metadata__:
        mode = __metadata__.get("function_calling", "default")
    is_native = (mode == "native")
```

> **Note :** `function_calling` est une clé top-level dans `__metadata__`, pas sous `params`. On trouve aussi `__model__["info"]["params"]["function_calling"]` dans la structure du modèle.

## `self.citation = True`

Active l'affichage du contexte de l'outil dans les réponses du frontend. Mettre à `False` pour utiliser des citations custom via `__event_emitter__`.

```python
class Tools:
    def __init__(self):
        self.citation = True  # Affiche le contexte automatiquement
```

> Source : Discussion GitHub #3134 — consultée le 13/04/2026

## Built-in System Tools (Native Mode uniquement)

| Catégorie | Outils | Description |
|-----------|--------|-------------|
| Search & Web | `search_web`, `fetch_url` | Requêtes web, extraction contenu URL |
| Knowledge Base | `list_knowledge`, `query_knowledge_files`, `view_file`, etc. | Navigation et extraction depuis les KB |
| Memory | `search_memories`, `add_memory`, `delete_memory` | Gestion de la personnalisation |
| Notes | `search_notes`, `write_note`, `view_note` | Opérations sur les notes utilisateur |
| Chat History | `search_chats`, `view_chat` | Accès historique conversations |
| Code Interpreter | `execute_code` | Exécution de code sandboxée |
| Image Generation | `generate_image`, `edit_image` | Création et modification d'images |
| Channels | `search_channels`, `view_channel_message` | Opérations sur les canaux |
| Time Tools | `get_current_timestamp`, `calculate_timestamp` | Calculs temporels |

**Exemple de signature :** `query_knowledge_files(query, knowledge_ids?, count=5)` → Retourne `Array of {content, source, file_id, distance?}`

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/ — consultée le 13/04/2026

## Exemples communautaires

### Recherche web (DuckDuckGo)

```python
from duckduckgo_search import DDGS

class Tools:
    def search_web(self, query: str) -> str:
        """Search web for query, return top 5 summaries."""
        try:
            results = DDGS().text(query, max_results=5)
            formatted = []
            for result in results:
                formatted.append(
                    f"Title: {result['title']}\n"
                    f"URL: {result['href']}\n"
                    f"Summary: {result['body']}"
                )
            return "\n---\n".join(formatted)
        except Exception as e:
            return f"Search error: {e}"
```

### Heure courante

```python
from datetime import datetime

class Tools:
    def get_current_time(self) -> str:
        """Get current time in human-readable format."""
        now = datetime.now()
        current_time = now.strftime("%I:%M:%S %p")
        current_date = now.strftime("%A, %B %d, %Y")
        return f"Current Date and Time = {current_date}, {current_time}"
```

### Requête SQL (avec Valves)

```python
import sqlite3
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        DB_PATH: str = Field(default="/path/db.sqlite3")
    
    def __init__(self):
        self.valves = self.Valves()
        self.citation = True
    
    def run_sql(self, query: str) -> str:
        """Execute read-only SQL query."""
        try:
            conn = sqlite3.connect(self.valves.DB_PATH)
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            return str(results)
        except Exception as e:
            return f"Error: {e}"
```

> Source : Discussion GitHub #3134 — consultée le 13/04/2026

## Modèles recommandés pour le function calling

- GPT-4o / GPT-5 (OpenAI)
- Claude 4.5 Sonnet (Anthropic)
- Gemini 3 Flash (Google)
- Llama 3.1-GROQ
- mistral-small:22b-instruct

Les modèles faibles (Llama 3 8B standard) échouent souvent à sélectionner le bon outil. Le modèle doit être entraîné sur des patterns de function-calling pour invoquer les outils de manière fiable. Le mode natif de tool calling dépend fortement de la capacité du modèle (Issue #9414).

> Source : Discussion GitHub #3134 + Issue #9414 — consultée le 13/04/2026
