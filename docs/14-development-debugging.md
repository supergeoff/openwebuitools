# Développement, test et débogage

## Méthodes de déploiement

### 1. Éditeur de code direct

Copier le code Python directement dans le workspace Open WebUI (Admin Panel → Workspace → Tools/Functions).

### 2. Marketplace communautaire

Importer depuis `openwebui.com/t/<username>` (Tools) ou `openwebui.com/f/<username>` (Functions).

> Source : Article Medium "Optimize Open WebUI" — consultée le 13/04/2026

### 3. Fichiers JSON

Convertir le fichier `.py` en format `.json` pour upload.

### 4. Pré-chargement avant premier démarrage (avancé)

Script d'entrypoint Docker qui :
1. Attend le démarrage d'Open WebUI
2. Crée l'admin via API signup
3. Enregistre les fonctions via `POST /api/v1/functions/create`

> **Note :** L'endpoint `/api/v1/functions/create` n'est pas listé dans la documentation API officielle.

**Structure de déploiement :**
```
├── webui/
│   ├── configs/
│   │   └── config_[locale].json
│   └── pipeline/
│       ├── mypipe_pipe.py
│       └── template.json
├── .service.webui.env
└── docker-compose.yml
```

> Source : Discussion GitHub #8955 — consultée le 13/04/2026

### Problème montage config.json

Monter directement `config.json` via volume Docker cause `OSError: [Errno 16] Device or resource busy` — l'application fait un `os.rename` incompatible avec les mounts. **Contournement :** utiliser le mécanisme de copie dans l'entrypoint plutôt que le montage direct de fichiers.

## Configuration Docker pour la persistance

```bash
docker run -d -p 3000:8080 --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --mount type=bind,source="<local_path>",target=/app/data \
  --name open-webui ghcr.io/open-webui/open-webui:cuda
```

Le bind mount "enables data exchange between isolated container and host system" — nécessaire pour que les extensions persistent des fichiers localement.

> Source : Article Medium "Optimize Open WebUI" — consultée le 13/04/2026

## Erreurs fréquentes et solutions

| Problème | Cause | Solution |
|----------|-------|----------|
| "Something went wrong :/ list index out of range" | Docstrings ou type hints manquants | Ajouter docstrings Sphinx-style complets et type hints |
| Tool jamais appelé par le modèle | Tool non activé pour le modèle | Activer dans workspace model settings |
| Tool absent de l'UI | Corruption du volume Docker | Reset du volume Docker (pas seulement le conteneur) |
| Tool appelé mais ne retourne rien | Modèle trop faible | Utiliser un modèle plus puissant (gpt-4o, Llama 3.1) |
| ImportError pour les packages | Dépendances non installées | Ajouter au frontmatter `requirements:` |
| `KeyError: 'type'` | Types complexes dans les signatures | Utiliser uniquement `str`, `int`, `float`, `bool` |
| Action supprime le message | `return body` au lieu de `return None` | Toujours retourner `None` depuis une Action |
| Caractères corrompus dans status descriptions | Bug i18n après v0.5.0 | Éviter les caractères spéciaux ou vérifier le rendu |
| __event_emitter__ ne fonctionne pas | Typé `None` au lieu de `Callable` | Utiliser `__event_emitter__=None` ou omettre le type |

> Source : Discussion GitHub #3134 + Issues diverses — consultées le 13/04/2026

## Débogage

### Logs Docker

```bash
docker logs open-webui
```

### Patterns de debugging recommandés

1. **Commencer simple** : tester avec des prompts directs ("Tell the LLM to use it")
2. **Consulter les logs** pour les détails d'exécution
3. **Vérifier les docstrings** : cause #1 d'erreurs silencieuses
4. **Vérifier les type hints** : uniquement `str`, `int`, `float`, `bool`
5. **Tester le mode Default d'abord** avant le mode Native

### Options pip supplémentaires

La variable d'environnement `PIP_OPTIONS` permet de contrôler le comportement de pip install pour les packages frontmatter :

```bash
PIP_OPTIONS="--upgrade --no-cache-dir"
```

## Bonnes pratiques communautaires

1. **Toujours inclure des docstrings** — "Without a docstring the calling LLM doesn't know what the function is for."
2. **Type hints obligatoires** sur tous les paramètres et retours (primitifs uniquement)
3. **Gestion d'erreurs** : wraper la logique dans try-except retournant des chaînes d'erreur significatives
4. **Tester localement** avant déploiement production
5. **Support async** : utiliser `async`/`await` pour les opérations réseau
6. **Limitation des résultats** pour ne pas surcharger le LLM
7. **`self.citation = True`** pour afficher le contexte des outils

> Source : Discussion GitHub #3134 — consultée le 13/04/2026

## Tool skeleton template

Le dépôt [open-webui-tool-skeleton](https://github.com/pahautelman/open-webui-tool-skeleton) propose un template de départ avec une classe utilitaire `EventEmitter` :

```python
class EventEmitter:
    def __init__(self, event_emitter):
        self.event_emitter = event_emitter

    async def progress_update(self, description):
        await self.emit(description, "progress")

    async def error_update(self, description):
        await self.emit(description, "error")

    async def success_update(self, description):
        await self.emit(description, "success")

    async def emit(self, description, status_type):
        if not self.event_emitter:
            return
        await self.event_emitter({
            "type": "status",
            "data": {
                "description": description,
                "done": status_type != "progress",
            },
        })
```

**Bonnes pratiques du template :**

| Pratique | Détail |
|----------|--------|
| Documentation | "Clear, detailed docstrings are the primary mechanism through which language models understand tool capabilities" |
| Design | Chaque méthode doit gérer une tâche spécifique et ciblée |
| Gestion d'erreurs | Gérer gracieusement les échecs API, inputs invalides, problèmes réseau via EventEmitter |
| Dépendances | Lister méticuleusement tous les packages externes dans le champ requirements |
| Sécurité | Valider et assainir tous les inputs fournis par le LLM ; restreindre les permissions |

> Source : https://github.com/pahautelman/open-webui-tool-skeleton — consultée le 13/04/2026

## Modèles recommandés pour le function calling

| Modèle | Mode recommandé |
|--------|----------------|
| GPT-4o / GPT-5 | Default + Native |
| Claude 4.5 Sonnet | Default + Native |
| Gemini 3 Flash | Default + Native |
| MiniMax M2.5 | Native |
| Llama 3.1-GROQ | Default |
| mistral-small:22b-instruct | Default |

Les modèles Llama 3 8B standard sont **connus pour être peu fiables** avec le tool calling natif (Issue #9414). Le mode Default est plus tolérant avec les modèles moins puissants.
