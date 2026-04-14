# Manques et imprécisions — Audit de la documentation

> Audit réalisé le 14/04/2026 par comparaison systématique des 16 fichiers docs/ avec les sources originales (lot1-3.md, plan.md) et les données Context7/GitHub.

---

## 1. Incohérences entre fichiers

### 1.1 `__event_call__` disponibilité
- **04-reserved-parameters.md** l.18 : indique `"Contexte action"` pour la disponibilité de `__event_call__`
- **06-event-system.md** l.23 : indique disponibilité dans Tools ✅, Actions ✅, Pipes ✅, Filters ✅
- **Verdict :** 04 est imprécis. `__event_call__` est disponible dans tous les types de fonctions, pas seulement les Actions.

### 1.2 `function_calling` dans `__metadata__` — chemin d'accès incohérent
- **04-reserved-parameters.md** l.57 : montre `"function_calling": "native"` comme clé top-level dans `__metadata__`
- **07-tools.md** l.156 : utilise `__metadata__.get("params", {}).get("function_calling", "default")` pour détecter le mode
- **Verdict :** Le chemin d'accès ne correspond pas. Soit `function_calling` est top-level, soit il est sous `params`. Le code source officiel (lot1 l.590) utilise le chemin `params.function_calling`, mais la structure de `__metadata__` documentée ne montre pas de clé `params`. Il faut clarifier quel chemin est correct, ou si les deux existent selon le contexte.

### 1.3 Événements `embeds`, `chat:message:error`, `chat:message:follow_ups` absents du tableau principal
- **06-event-system.md** l.47 : `embeds` apparaît dans le tableau de persistance mais **pas** dans le tableau de référence des types d'événements (l.27-41)
- **06-event-system.md** l.48 : `chat:message:error` et `chat:message:follow_ups` apparaissent dans les non-persistés mais **pas** dans le tableau de référence
- **Verdict :** Le tableau de référence est incomplet. Ajouter ces 3 types avec leur helper et data structure.

### 1.4 Action : retour `None` vs `dict` — ambiguïté
- **10-actions.md** l.20 : montre `return {"content": "Modified message content"}` comme exemple de structure de base
- **10-actions.md** l.80-91 : dit "Toujours retourner None pour éviter la suppression de message"
- **Verdict :** Les deux instructions sont contradictoires sans explication. Il manque la distinction : retourner `None` = ne pas modifier le message ; retourner `{"content": "..."}` = remplacer le contenu du message ; retourner `body` = supprime le message (bug). Il faut clarifier les 3 cas.

---

## 2. Informations manquantes par rapport au matériel source

### 2.1 02-extension-taxonomy.md
- **Manque :** "Python 3.11 requis" pour les Pipelines externes (mentionné dans lot1 §1.2)
- **Manque :** La citation complète de la définition de Tool : "Python scripts that run directly within the Open WebUI environment" (lot1 §1.1 — seul un résumé est donné)
- **Imprécision :** Le tableau comparatif dit "Via frontmatter `requirements`" pour l'import de packages des Functions internes, mais le lot1 source précise "pas d'import de packages supplémentaires natif (sauf via frontmatter requirements)" — la nuance est importante car l'import via frontmatter est un mécanisme runtime pip install, pas un vrai import Python

### 2.2 03-architecture-lifecycle.md
- **Manque :** Les méthodes `_get_access_grants()` et `get_tools_by_user_id()` du CRUD Tools (lot1 §10.2)
- **Manque :** Le scaffold `function_calling_scaffold.py` (4ème scaffold listé dans lot2 §7.4 et dans le plan)
- **Imprécision :** Le code scaffold Pipeline importe `from schemas import OpenAIChatMessage` — ce module n'existe que dans le contexte Pipelines, pas dans Open WebUI main. Il faudrait le noter.
- **Manque :** Le scaffold Filter Pipeline a un frontmatter metadata (title, author, date, version, license, description, requirements) dans le code source original qui n'est pas reproduit

### 2.3 04-reserved-parameters.md
- **Manque :** La structure détaillée de `__tools__` (ToolUserModel) — le type est mentionné mais aucun champ n'est documenté
- **Manque :** La structure de `__oauth_token__` — décrit comme "dict" mais aucun champ listé
- **Manque :** Le comportement quand un paramètre réservé est demandé mais non disponible (ex: `__event_call__` dans un contexte sans connexion live) — que se passe-t-il ? None ? Erreur ?

### 2.4 05-valves.md
- **Manque :** La méthode `get_model_options` des dropdowns dynamiques reçoit `__user__=None` — le fait que ce paramètre soit injecté automatiquement (comme les reserved args) n'est pas expliqué
- **Manque :** Le comportement d'un champ `required=True` quand il est vide — y a-t-il validation côté UI ? Côté backend ?
- **Manque :** La différence de persistance entre Valves (colonne `valves` dans la table function/tool) et UserValves (stockées dans `user.settings.functions.valves[function_id]`) est mentionnée mais le mécanisme de lecture/écriture n'est pas détaillé

### 2.5 06-event-system.md
- **Manque :** La structure de données de l'événement `source` (distinct de `citation`) — le tableau dit "Open WebUI Source/Citation Object" mais seul `citation` est détaillé dans l'exemple
- **Manque :** Les champs metadata personnalisables dans les citations (ex: `type` comme "academic_journal", "database_record" ; `journal`, `volume`, `pages`, `doi` pour les citations académiques) — documentés via Context7 mais pas inclus
- **Manque :** L'événement `embeds` — listé dans la persistance mais pas dans le tableau de référence
- **Manque :** Le format exact du payload pour l'endpoint REST des événements externes (`POST /api/v1/chats/{chat_id}/messages/{message_id}/event`)

### 2.6 07-tools.md
- **Manque :** Le modèle Gemini 1.5 listé dans la discussion #3134 comme recommandé pour le function calling
- **Manque :** La variable d'environnement `PIP_OPTIONS` pour contrôler le comportement de pip install (documentée via Context7)
- **Imprécision :** Voir §1.2 sur le chemin `function_calling` dans `__metadata__`

### 2.7 08-pipes.md
- **Manque :** Les autres paramètres injectables dans `pipe()` (`__event_emitter__`, `__metadata__`, `__tools__`, etc.) — seuls body, `__user__`, `__request__` sont listés
- **Manque :** Comment un Pipe sans `pipes()` apparaît dans l'UI (comme un modèle unique avec le nom du Pipe)
- **Manque :** L'utilisation de `__tools__` dans un Pipe pour appeler d'autres outils — pattern puissant mais non documenté

### 2.8 09-filters.md
- **Manque :** Les méthodes `inlet`, `stream`, `outlet` peuvent aussi être async (seul `inlet` est montré async dans l'exemple)
- **Manque :** Dans le contexte Pipelines, les filtres ont `self.type = "filter"` et une valve `pipelines` pour cibler des pipelines spécifiques (pont entre 03 et 09)
- **Imprécision :** `outlet()` retourne `None` selon la doc, mais le bug #8168 montre qu'il peut retourner `body` (dict). Le comportement réel est : peut retourner body modifié ou None, mais les modifications de body peuvent être annulées par un bug résolu. La documentation actuelle est trop catégorique.

### 2.9 10-actions.md
- **Manque :** La distinction claire entre `return None`, `return {"content": "..."}`, et `return body` (voir §1.4)
- **Manque :** L'Action reçoit aussi `__metadata__`, `__chat_id__`, `__message_id__` etc. — pas seulement les paramètres montrés
- **Manque :** Où définir la liste `actions` — comme attribut de classe ? Dans `__init__` ? Ce n'est pas clair.

### 2.10 11-rich-ui.md
- **Bug code :** l.42 : `return HTMLResponse(content=html_content, headers=headers), result_context` — la variable `headers` n'est pas définie dans cet extrait. Il faut ajouter `headers = {"Content-Disposition": "inline"}`.
- **Manque :** Le comportement au rechargement d'un chat historique — le HTML est-il re-rendu depuis le code sauvegardé ? Est-ce mis en cache ?

### 2.11 12-external-tools.md
- **Manque :** Le JSON de configuration MCP programmatique (ex: config Notion avec `"type": "mcp"`, `"auth_type": "oauth_2.1"` — documenté via Context7 mais pas inclus)
- **Manque :** La FAQ MCP sur la stabilité : "Supported and improving. The broader ecosystem is still evolving; expect occasional breaking changes."
- **Manque :** Le flag `--host` de mcpo pour le déploiement Docker (visible dans le Dockerfile mais pas expliqué)
- **Manque :** Le format de configuration `TOOL_SERVER_CONNECTIONS` supporte aussi le type `"mcp"`

### 2.12 13-security.md
- **Manque :** Les risques spécifiques liés à `allowSameOrigin` ON pour les Rich UI embeds — un iframe avec same-origin peut accéder cookies, localStorage, DOM du parent, ce qui est un vecteur XSS si le contenu n'est pas de confiance
- **Manque :** Le flag `--add-host=host.docker.internal:host-gateway` dans la commande Docker Pipeline est un risque potentiel (accès à l'hôte depuis le conteneur)

### 2.13 14-development-debugging.md
- **Bug typo :** l.72 : `=__event_emitter__=None` devrait être `__event_emitter__=None` (le `=` initial est en trop)
- **Manque :** La variable d'environnement `PIP_OPTIONS` (ex: `PIP_OPTIONS="--upgrade --no-cache-dir"`) pour contrôler pip install

### 2.14 15-migrations.md
- **Manque :** Un exemple d'utilisation de `get_async_db_context` avec `AsyncSession` (mentionné mais pas montré)
- **Manque :** Les migrations intermédiaires entre 0.5 et 0.8.12 (il peut y avoir eu des breaking changes non documentés)
- **Manque :** La mention que `Users.get_user_by_id()` est passé de sync à async en 0.9.0 est dans 08-pipes.md mais pas dans 15-migrations.md

### 2.15 16-known-issues-resources.md
- **Manque :** Le scaffold `function_calling_scaffold.py` dans la liste des scaffolds
- **Manque :** Le pattern de chiffrement `encrypted:` prefix du dépôt owndev/Open-WebUI-Functions
- **Manque :** L'exigence Python 3.8+ du dépôt Haervwe/open-webui-tools

---

## 3. Informations du matériel source non couvertes

| Information source | Emplacement source | Statut dans la nouvelle doc |
|---|---|---|
| DeepWiki — données NON trouvées (mécanisme exec/eval, hot-reload, gestion erreurs, versionnage) | lot2 §6.1 | ❌ Absent — ces lacunes de la documentation officielle ne sont pas signalées |
| Plan §5 — données à collecter en amont (liste complète de prérequis) | plan.md §5 | ❌ Absent — les prérequis de collecte ne sont pas résumés |
| Issue #11750 détails | lot3 §8.1 | ⚠️ Mentionné comme "Non résolu (?)" mais détails non collectés |
| owndev/Open-WebUI-Functions — détails Azure AI (catalogue modèles, auth flexible, token tracking) | lot2 §7.2 | ❌ Très résumé — les patterns spécifiques (chiffrement clés, BM25+semantic rerank) manquent |
| Haervwe — détails Planner Agent v3, Letta Agent | lot2 §7.3 | ❌ Noms listés mais aucun détail d'architecture |
| Article Medium "Beyond Text" contenu technique | lot3 §10.1 | ❌ Paywall — non collectable, mais devrait être signalé comme lacune connue |
| open-webui/openapi-servers — contenu des serveurs (filesystem, memory, time) | lot2 §7.4 | ❌ Seul le time server est montré en quickstart |

---

## 4. Problèmes de qualité rédactionnelle

| Fichier | Problème |
|---|---|
| 03-architecture-lifecycle.md | Le schéma de flux vient de DeepWiki (source IA-générée) — le plan.md prévient explicitement de sa fiabilité limitée, mais aucun avertissement n'est inclus |
| 07-tools.md + 04-reserved-parameters.md | Voir §1.2 — incohérence sur le chemin `function_calling` dans `__metadata__` |
| 06-event-system.md | Le tableau de référence des événements est incomplet (embeds, error, follow_ups manquants) |
| 11-rich-ui.md | Variable `headers` non définie dans l'exemple de tuple |
| 14-development-debugging.md | Typo `=__event_emitter__=None` |

---

## 5. Synthèse des priorités de correction

### Critique (incohérences entre fichiers)
1. §1.1 — `__event_call__` disponibilité dans 04 vs 06
2. §1.2 — Chemin `function_calling` dans `__metadata__` incohérent entre 04 et 07
3. §1.4 — Action retour None vs dict — contradiction dans 10

### Important (informations manquantes du matériel source)
4. §2.5 — Types d'événements manquants dans le tableau de référence (embeds, error, follow_ups)
5. §2.6 — Citation metadata personnalisables (type, journal, doi, etc.)
6. §2.7 — Paramètres injectables complets dans `pipe()`
7. §2.9 — Clarification Action return None / dict / body
8. §2.10 — Bug code headers non définies dans 11-rich-ui.md

### Mineur mais utile
9. §2.1 — Python 3.11 requis pour Pipelines
10. §2.3 — Structure de `__tools__` et `__oauth_token__`
11. §2.13 — Typo dans 14-development-debugging.md
12. §2.12 — Configuration MCP programmatique (JSON example)
13. §2.15 — Scaffold function_calling manquant dans la liste
