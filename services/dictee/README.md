# Proxy de dictée

Ce service se place entre Open WebUI et un serveur de reconnaissance vocale compatible OpenAI, comme speaches. Il transmet la requête de transcription sans la modifier, puis fait nettoyer le texte obtenu par un modèle de langage, via une passerelle compatible OpenAI comme LiteLLM. Le texte nettoyé arrive dans la zone de saisie d'Open WebUI, où l'utilisateur peut encore le corriger avant l'envoi.

Quand le nettoyage échoue, dépasse le délai ou s'écarte trop du texte d'origine, le proxy renvoie la transcription brute. La dictée ne casse donc jamais à cause du modèle de langage. La spec complète se trouve dans `docs/superpowers/specs/2026-10-24-dictee-design.md`.

## Variables d'environnement

| Variable | Rôle | Exemple |
|---|---|---|
| `SPEACHES_URL` | Base de l'API de reconnaissance vocale | `http://speaches:8000/v1` |
| `LITELLM_URL` | Base de l'API de la passerelle LLM | `http://litellm:4000/v1` |
| `LITELLM_API_KEY` | Clé de la passerelle, limitée au modèle de nettoyage | |
| `CLEANUP_MODEL` | Modèle de nettoyage (par défaut `flash-low`) | `flash-low` |
| `GLOSSARY_FILE` | Chemin du glossaire (par défaut `/app/glossary.txt`) | `/app/glossary.txt` |

Le proxy n'a pas besoin de la clé du serveur de reconnaissance vocale. Il transmet l'en-tête `Authorization` envoyé par Open WebUI.

## Glossaire

Le glossaire contient une entrée par ligne. Une entrée donne un terme, suivi si besoin de ses déformations connues, par exemple `Parakeet (often heard as: parachit, pas repeat)`. Ces déformations aident beaucoup le modèle quand un terme est mal entendu en plusieurs mots. Les lignes vides et celles qui commencent par `#` sont ignorées. Le fichier est relu à chaque requête, donc une modification s'applique sans redémarrage. Il reste hors de ce dépôt, parce que ses termes sont propres à chaque utilisateur.

## Lancement

Le fichier `app.py` déclare ses dépendances dans son en-tête (PEP 723). Une seule commande suffit pour le lancer, avec l'image `ghcr.io/astral-sh/uv` :

```bash
uv run /app/app.py
```

Le service écoute sur le port 8000 et expose `POST /v1/audio/transcriptions` et `GET /health`. Dans Open WebUI, l'URL de base du STT pointe vers ce service, suivie de `/v1`, et la clé STT reste celle du serveur de reconnaissance vocale.

## Mise à jour

Ce dépôt sert de source. Pour déployer une nouvelle version, il faut réécrire le montage `app.py` du compose avec le contenu du fichier, puis redéployer le compose.

## Tests

Les tests se trouvent dans `tests/test_dictee.py`. Ils demandent les mêmes versions de `starlette`, `httpx` et `uvicorn` que l'en-tête de `app.py` :

```bash
python -m unittest tests.test_dictee
```
