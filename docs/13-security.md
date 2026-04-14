# Sécurité, limites et bonnes pratiques

## Exécution de code arbitraire

"Workspace Tools and Functions execute arbitrary Python code on your server."

**Équivalence shell :** "Granting a user the ability to create or import Tools is equivalent to giving them shell access."

**Restriction :** La création de fonctions/tools est restreinte aux administrateurs.

> Source : https://docs.openwebui.com/features/extensibility/plugin/tools/development/ — consultée le 13/04/2026

## Répertoire de données

Dans Docker : `/app/backend/data`

> Source : https://docs.openwebui.com/features/extensibility/plugin/ — consultée le 13/04/2026

## Risques liés au JavaScript non sandboxé

Les événements `execute` (via `__event_call__` ou `__event_emitter__`) exécutent du JavaScript dans le **contexte de la page principale**, sans iframe sandbox :

"JavaScript runs in main page context with full DOM, cookie, and localStorage access—no iframe sandboxing"

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/events — consultée le 13/04/2026

**Recommandation :** Ne jamais exécuter de code JavaScript non fiable via les événements execute. Préférer le Rich UI Embed (iframe sandboxé) pour le contenu HTML.

## Risques liés à allowSameOrigin pour les Rich UI embeds

L'activation de `allowSameOrigin` (Settings → Interface → Allow Iframe Same-Origin Access) permet à l'iframe d'accéder aux cookies, localStorage et DOM du parent. **C'est un vecteur XSS si le contenu HTML embarqué n'est pas de confiance.**

**Recommandation :** Ne jamais activer `allowSameOrigin` avec du contenu provenant de sources non fiables.

## Risques du flag Docker `--add-host`

Le flag `--add-host=host.docker.internal:host-gateway` utilisé dans les commandes Docker Pipeline et Open WebUI permet au conteneur d'accéder aux services de la machine hôte. C'est un risque potentiel en production si le conteneur est compromis.

**Recommandation :** En production, limiter l'accès réseau du conteneur et utiliser des réseaux Docker dédiés plutôt que l'accès hôte direct.

## Risques des Pipelines

"A malicious Pipeline could access your file system, exfiltrate data, mine cryptocurrency, or compromise your system."

Les Pipelines s'exécutent dans leur propre conteneur mais ont un accès complet au système de fichiers et réseau de ce conteneur.

> Source : https://docs.openwebui.com/features/extensibility/pipelines/ — consultée le 13/04/2026

## Fuite de données via `functools.partial` (Issue #16307)

**Problème :** Quand les méthodes d'un tool sont async et acceptent `__user__`/`__event_emitter__`, le dict `__tools__` passé aux pipes contient un `functools.partial` qui expose l'objet utilisateur complet et les données sensibles.

**Données exposées :** Clés API (`sk-...`), images de profil en base64, mots de passe d'outils email, configurations complètes des valves, paramètres système.

**Comportement non-async (attendu) :**
```python
'callable': <function Tools.get_temperature at 0x7f2fbb1ac860>
```

**Comportement async (problématique) :**
```python
'callable': functools.partial(
    <bound method Tools.get_temperature>,
    __event_emitter__=<function>,
    __user__={...full user dict...}
)
```

**Statut :** Fermé comme "intended behaviour", mais les implications sécurité nécessitent reconsidération.

**Recommandation :** Les implémentations de Pipe doivent **manuellement filtrer les données sensibles** avant d'envoyer les informations d'outils à des fournisseurs LLM externes. Le framework passe l'état interne complet via les closures partial.

> Source : Issue #16307 — consultée le 13/04/2026

## Typage de `__event_emitter__`

Le typage doit être `Callable` ou omis (pour l'injection automatique), **jamais `None`** :

```python
# INCORRECT — casse l'injection
async def my_method(self, __event_emitter__: None):

# CORRECT
async def my_method(self, __event_emitter__=None):
```

> Source : Issue #8168 — consultée le 13/04/2026

## Pip install runtime — risques en production

`ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=True` (défaut) permet l'installation arbitraire de packages par des outils tiers.

**Risques :**
- Installation de packages malveillants
- Race conditions avec `UVICORN_WORKERS > 1` ou replicas multiples (pip locking)
- UI non responsive pendant l'installation

**Recommandation production :**

```bash
ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=False
```

Pré-installer via Dockerfile :

```dockerfile
FROM ghcr.io/open-webui/open-webui:main
RUN pip install --no-cache-dir python-docx requests beautifulsoup4
```

> Source : Context7 (/open-webui/docs) — consultée le 13/04/2026

## Recommandations de sécurité

1. **Restreindre la création de Tools/Functions aux administrateurs** — configuration par défaut, à maintenir
2. **Ne jamais installer d'outils depuis des sources non fiables** — toujours revoir le code avant import
3. **Désactiver le pip install runtime en production**
4. **Filtrer manuellement les données sensibles** dans les Pipes avant envoi aux LLMs externes
5. **Préférer le Rich UI Embed (iframe sandboxé)** aux événements execute pour le contenu HTML
6. **Valider et assainir tous les inputs** fournis par le LLM
7. **Restreindre les permissions** pour les opérations fichiers/commandes
8. **Ne pas monter directement config.json** via volume Docker (provoque `OSError: [Errno 16]` via `os.rename`) — utiliser un script d'entrypoint à la place
9. **En production, servir les OpenAPI tool servers en HTTPS** — les navigateurs bloquent les requêtes HTTP depuis des pages HTTPS
