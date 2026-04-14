# Corpus documentaire — Open WebUI : Création d'outils custom
## LOT 3 : Sources 8 à 11 (Issues/Discussions GitHub, Tool Skeleton, Articles, Discord)

**Version cible :** Open WebUI v0.8.12 (publiée le 27 mars 2025)
**Date de collecte :** 13 avril 2026

---

# SOURCE 8 : DISCUSSIONS ET ISSUES GITHUB

**URL :** https://github.com/open-webui/open-webui/discussions et /issues
**Ce qu'on y cherche :** Problèmes connus, bugs documentés, retours d'expérience, limites actuelles.

## 8.1 Issues relatives à __event_emitter__

### Issue #8168 — __event_emitter__ et persistance du contenu dans outlet (RÉSOLUE)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | v0.5.2 | https://github.com/open-webui/open-webui/issues/8168 | 28/12/2024 |
| Bug 1 | `__event_emitter__` ne fonctionne pas dans la méthode `outlet` des filtres | https://github.com/open-webui/open-webui/issues/8168 | 28/12/2024 |
| Bug 2 | Modifications de `body["messages"][-1]["content"]` dans outlet sont annulées — le texte modifié apparaît brièvement puis revient à la sortie originale du modèle | https://github.com/open-webui/open-webui/issues/8168 | 28/12/2024 |
| Résolution | FERMÉ COMPLÉTÉ — PR #8159 merged. Corrigé dans les versions dev. | https://github.com/open-webui/open-webui/issues/8168 | 28/12/2024 |

**Code problématique :**
```python
async def outlet(
    self,
    body: dict,
    __event_emitter__: None,  # ← typage incorrect (None au lieu de Callable)
    __user__: Optional[dict] = None,
    __model__: Optional[dict] = None,
) -> dict:
    body["messages"][-1]["content"] = "TEST"
    return body
```

**Leçon pour le corpus :** Le typage du paramètre `__event_emitter__` doit être `Callable` ou omis (pour l'injection automatique), pas `None`. Le comportement de revert dans outlet était un bug d'implémentation résolu.

### Issue #8292 — __event_emitter__ pour les Action functions (RÉSOLUE)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | Non spécifiée (fin 2024) | https://github.com/open-webui/open-webui/issues/8292 | 03/01/2025 |
| Bug | `__event_emitter__` échoue dans les Actions avec exception `'user_id'` — le contexte utilisateur n'est pas correctement transmis | https://github.com/open-webui/open-webui/issues/8292 | 03/01/2025 |
| Résolution | FERMÉ COMPLÉTÉ — PR #8246 merged le 5 janvier 2025 | https://github.com/open-webui/open-webui/issues/8292 | 03/01/2025 |
| Finding additionnel | Les Actions doivent retourner `None` plutôt que `return body` — retourner le body supprime le message | https://github.com/open-webui/open-webui/issues/8292 | 03/01/2025 |

**Leçon pour le corpus :** Toujours retourner `None` depuis une Action function pour éviter la suppression de message.

### Issue #11750 — Erreur pipe function lors de l'appel à __event_emitter__

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Date | 17 mars 2025 | https://github.com/open-webui/open-webui/issues/11750 | 17/03/2025 |
| Bug | Les pipe functions rencontrent des erreurs lors de l'appel à `__event_emitter__` | https://github.com/open-webui/open-webui/issues/11750 | 17/03/2025 |

**Note :** Détails non collectés en profondeur — à recouper si nécessaire.

### Issue #8129 — Caractères corrompus dans les Status descriptions après v0.5.0

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Bug | Les descriptions de status contenant certains caractères sont corrompues par le système i18n après v0.5.0 | https://github.com/open-webui/open-webui/issues/8129 | Date non collectée |

**Leçon pour le corpus :** Éviter les caractères spéciaux dans les descriptions de status events, ou vérifier le rendu après mise à jour.

## 8.2 Issues relatives aux Tools et au Function Calling

### Issue #16307 — __tools__ dans pipe expose les paramètres internes quand async (SÉCURITÉ)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | Non spécifiée (août 2025) | https://github.com/open-webui/open-webui/issues/16307 | 05/08/2025 |
| Bug | Quand les méthodes d'un tool sont async et acceptent `__user__`/`__event_emitter__`, le dict `__tools__` passé aux pipes contient un `functools.partial` qui expose l'objet utilisateur complet et les données sensibles | https://github.com/open-webui/open-webui/issues/16307 | 05/08/2025 |
| Données exposées | Clés API (`sk-...`), images de profil en base64, mots de passe d'outils email, configurations complètes des valves, paramètres système | https://github.com/open-webui/open-webui/issues/16307 | 05/08/2025 |
| Résolution | FERMÉ — marqué comme "intended behaviour", mais les implications sécurité nécessitent reconsidération | https://github.com/open-webui/open-webui/issues/16307 | 06/08/2025 |

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

**Leçon pour le corpus :** Les implémentations de Pipe doivent manuellement filtrer les données sensibles avant d'envoyer les informations d'outils à des fournisseurs LLM externes. Le framework passe l'état interne complet via les closures partial.

### Issue #9414 — Le modèle ne fait rien avec le résultat d'un native tool call

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | Open WebUI 0.5.9, Ollama 0.5.7 | https://github.com/open-webui/open-webui/issues/9414 | Date non collectée |
| Bug | Après l'exécution réussie d'un tool en mode natif, le modèle ne génère aucune réponse. Le message reste vide avec seulement les détails du tool call. | https://github.com/open-webui/open-webui/issues/9414 | Date non collectée |
| Résolution | FERMÉ — "llama3 models are known for being unreliable" avec le tool calling natif. Converti en discussion #9435. | https://github.com/open-webui/open-webui/issues/9414 | Date non collectée |

**Leçon pour le corpus :** Le mode natif de tool calling dépend fortement de la capacité du modèle. Les modèles Llama 3 standard sont connus pour être peu fiables dans ce mode. Recommander des modèles frontier (GPT-4o, Claude, Gemini) pour le native tool calling.

### Issue #17366 — Citations multiples fusionnées en une seule source

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | v0.6.28 | https://github.com/open-webui/open-webui/issues/17366 | 11/09/2025 |
| Bug | Plusieurs événements citation émis par un outil sont fusionnés en une seule source au lieu d'être affichés séparément | https://github.com/open-webui/open-webui/issues/17366 | 11/09/2025 |
| Résolution | FERMÉ — "Intended behaviour, same id should be merged". Le champ qui détermine le groupement n'est pas clarifié. | https://github.com/open-webui/open-webui/issues/17366 | 11/09/2025 |

**Leçon pour le corpus :** Pour afficher des citations distinctes, s'assurer que les identifiants de chaque citation sont différents. Le mécanisme de groupement n'est pas documenté explicitement — à tester empiriquement.

### Issue #19169 — Duplication du system prompt pendant les appels d'outils agentic

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Bug | Duplication du system prompt lors des tool calls agentic, causant un gaspillage de tokens et un surcoût du cache d'écriture | https://github.com/open-webui/open-webui/issues/19169 | Date non collectée |

### Issue #19250 — Support SSE pour les status events des serveurs agentic

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Feature request | Permettre aux événements status générés via SSE de mettre à jour la zone de status intégrée pour les serveurs agentic | https://github.com/open-webui/open-webui/issues/19250 | Date non collectée |

### Issue #20892 — Support des événements pour les outils externes (OpenAPI/MCP)

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Feature request | Les outils externes (OpenAPI/MCP) n'ont pas la même disponibilité des fonctions `event_emitter` et `event_call` que les outils Python natifs | https://github.com/open-webui/open-webui/issues/20892 | 23/01/2026 |

## 8.3 Discussions pertinentes

### Discussion #3134 — Guide d'utilisation des Tools

(Déjà documenté au Lot 2, section 7.5)

### Discussion #13174 — TypeError lors de l'exécution d'un custom Tool

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Version affectée | v0.6.5 | https://github.com/open-webui/open-webui/discussions/13174 | Date non collectée |
| Problème | Le tool-schema builder d'Open WebUI ne supporte que 4 types primitifs : `str`, `int`, `float`, `bool` | https://github.com/open-webui/open-webui/discussions/13174 | Date non collectée |
| Types non supportés | `Optional[str]`, `Dict[str, Any]`, `Union[int, str]`, `List[...]` | https://github.com/open-webui/open-webui/discussions/13174 | Date non collectée |
| Conséquence | Le schema builder crée un objet JSON manquant le champ obligatoire "type", provoquant `KeyError: 'type'` avant que le LLM n'accède à l'outil | https://github.com/open-webui/open-webui/discussions/13174 | Date non collectée |
| Solution | Remplacer tous les type hints complexes par des primitifs. Convertir `Optional[]` en valeurs par défaut, supprimer `Dict`, `List`, `Union` | https://github.com/open-webui/open-webui/discussions/13174 | Date non collectée |

**Leçon critique pour le corpus :** Les signatures de méthodes des Tools ne supportent que `str`, `int`, `float`, `bool` comme type hints. Tout type complexe (`Optional`, `Dict`, `List`, `Union`) provoque des erreurs silencieuses ou des `KeyError`. C'est une limitation fondamentale à documenter en priorité.

### Discussion #8955 — Pré-charger des Tools/Functions avant le premier démarrage

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Solution | Script d'entrypoint Docker qui attend le démarrage, crée l'admin via API signup, puis enregistre les fonctions via `POST /api/v1/functions/create` | https://github.com/open-webui/open-webui/discussions/8955 | Date non collectée |
| API non documentée | L'endpoint `/api/v1/functions/create` n'est pas listé dans la documentation API officielle | https://github.com/open-webui/open-webui/discussions/8955 | Date non collectée |
| Problème montage config | Monter directement `config.json` via volume Docker cause `OSError: [Errno 16] Device or resource busy` — l'application fait un `os.rename` incompatible | https://github.com/open-webui/open-webui/discussions/8955 | Date non collectée |
| Contournement | Utiliser le mécanisme de copie dans l'entrypoint plutôt que le montage direct de fichiers | https://github.com/open-webui/open-webui/discussions/8955 | Date non collectée |

**Structure de déploiement proposée :**
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

### Discussion #16415 — Simplifier l'écosystème Tools et Functions

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Problème identifié | 5 catégories distinctes créent la confusion : Capabilities, Tools, Tool Servers, Functions (Filters/Actions/Pipes), Pipelines | https://github.com/open-webui/open-webui/discussions/16415 | Date non collectée |
| Confusion nomenclature | "Tools" et "Capabilities" font des choses similaires avec des termes différents. "Tool settings" et "Tool server settings" partagent le label "Tools" | https://github.com/open-webui/open-webui/discussions/16415 | Date non collectée |
| Décalage doc/UI | La structure de la documentation ne correspond pas à l'organisation de l'UI. Ex : la doc met "Filters" et "Pipes" sous "Pipelines", mais l'UI les place sous "Functions" | https://github.com/open-webui/open-webui/discussions/16415 | Date non collectée |
| Sur-agrégation | "Functions" combine 3 opérations avec des workflows utilisateur fondamentalement différents | https://github.com/open-webui/open-webui/discussions/16415 | Date non collectée |
| Solution proposée | Fusionner "capabilities", "tools" et "tool servers" sous "tools" unifié avec sous-catégories. Désagréger "Functions" en catégories nommées distinctes. | https://github.com/open-webui/open-webui/discussions/16415 | Date non collectée |

**Leçon pour le corpus :** La confusion taxonomique est reconnue par la communauté. Le corpus doit clarifier rigoureusement la taxonomie dès la section 2 et signaler les incohérences entre documentation et interface.

### Discussion #17788 — Support d'éléments UI custom dans les messages chat

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Question | Peut-on intégrer des éléments UI custom (formulaires, boutons, résultats formatés) directement dans les messages chat ? | https://github.com/open-webui/open-webui/discussions/17788 | Date non collectée |
| Réponse | Oui, possible via la fonctionnalité Tools (Rich UI Embedding avec HTMLResponse) | https://github.com/open-webui/open-webui/discussions/17788 | Date non collectée |
| Limitation | Les Artifacts (alternative) se rendent dans des sidebars, pas inline avec les messages | https://github.com/open-webui/open-webui/discussions/17788 | Date non collectée |

---

# SOURCE 9 : DÉPÔT open-webui-tool-skeleton

**URL :** https://github.com/pahautelman/open-webui-tool-skeleton
**Ce qu'on y cherche :** Template de départ, structure de fichier, bonnes pratiques annotées.

## 9.1 Informations générales

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Description | Template fondationnel pour le développement d'outils custom Open WebUI | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |
| Stars / Forks | 10 stars, 2 forks | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |
| Date de création | 25 avril 2025 | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |
| Licence | MIT | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |
| Langage | Python 100% | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |

## 9.2 Structure du template

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Fichiers | `README.md` + `tool-skeleton.py` (2 fichiers uniquement) | https://github.com/pahautelman/open-webui-tool-skeleton | consultée le 13/04/2026 |

## 9.3 Composants clés du template

### Contenu détaillé — Metadata (docstring top-level) :
Chaque fichier tool commence par un bloc metadata triple-quote :
- `title` : Nom user-friendly affiché dans l'UI
- `author` : Nom/handle du créateur
- `author_url` : Lien optionnel vers le profil
- `git_url` : Lien optionnel vers le repo source
- `description` : Explication brève des fonctionnalités
- `required_open_webui_version` : Version minimum requise
- `requirements` : Liste de packages pip séparés par des virgules
- `version` : Numéro de version de l'outil
- `license` : Licence de distribution

### Contenu détaillé — Structure de la classe Tools :
```python
class Tools:
    def __init__(self):
        self.valves = self.Valves()       # Config admin
        self.user_valves = self.UserValves()  # Config utilisateur
    
    class Valves(BaseModel):
        api_key: str = Field(default="", description="API Key")
        priority: int = Field(default=0, description="Priority")
    
    class UserValves(BaseModel):
        show_status: bool = Field(default=True, description="Show status")
    
    async def tool_method(self, param: str, __event_emitter__: Callable[[dict], Any] = None) -> str:
        """
        Description complète.
        :param param: Description du paramètre.
        :return: Description du retour.
        """
        # implementation
```

### Contenu détaillé — Classe EventEmitter helper :
Le template inclut une classe utilitaire `EventEmitter` avec les méthodes :
- `progress_update(description)` : Rapporte un statut en cours
- `error_update(description)` : Rapporte une erreur
- `success_update(description)` : Rapporte une complétion
- `emit()` : Méthode core envoyant les données de status

### Contenu détaillé — Exemple d'implémentation (String Inverse Tool) :
L'exemple inclus :
1. Définit metadata avec title "String Inverse"
2. Crée Valves avec mock API key et priority
3. Crée UserValves avec toggle booléen
4. Implémente `reverse_string()` qui :
   - Valide la clé API via configuration valve
   - Utilise EventEmitter pour le reporting de status
   - Retourne la string inversée via Python slicing

### Contenu détaillé — Bonnes pratiques documentées :

| Pratique | Détail |
|----------|--------|
| Documentation | "Clear, detailed docstrings are the primary mechanism through which language models understand tool capabilities" |
| Design | Chaque méthode doit gérer une tâche spécifique et ciblée |
| Gestion d'erreurs | Gérer gracieusement les échecs API, inputs invalides, problèmes réseau via EventEmitter `error_update()` |
| Dépendances | Lister méticuleusement tous les packages externes dans le champ requirements |
| Sécurité | Valider et assainir tous les inputs fournis par le LLM ; restreindre les permissions pour les opérations fichiers/commandes |

**Source :** https://github.com/pahautelman/open-webui-tool-skeleton — consultée le 13/04/2026

**Évaluation de la source :** Dépôt minimaliste (2 fichiers) mais utile comme point de départ. Compatible avec la documentation officielle. Dernier commit : avril 2025. L'approche EventEmitter helper est un pattern propre non présent dans la doc officielle — utile comme best practice.

---

# SOURCE 10 : ARTICLES MEDIUM / BLOGS TECHNIQUES

## 10.1 Article Medium (paywall) — "Beyond Text: Equipping Your Open WebUI AI with Action Tools"

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Titre | Beyond Text: Equipping Your Open WebUI AI with Action Tools | https://medium.com/@hautel.alex2000/beyond-text-equipping-your-open-webui-ai-with-action-tools-594e15cd7903 | 25/04/2025 |
| Auteur | Peter Alexandru Hautelman | https://medium.com/@hautel.alex2000/beyond-text-equipping-your-open-webui-ai-with-action-tools-594e15cd7903 | 25/04/2025 |
| Statut | Contenu derrière paywall Medium ("Member-only story") — seuls les métadonnées et le sommaire ont été collectés | https://medium.com/@hautel.alex2000/beyond-text-equipping-your-open-webui-ai-with-action-tools-594e15cd7903 | 25/04/2025 |
| Version gratuite | URL blog personnel : `pahautelman.github.io/pahautelman-blog/tutorials/open-webui-action-tools/` — 404 au moment de la collecte | N/A | consultée le 13/04/2026 |

**Sommaire de l'article :**
1. Introduction to Open WebUI Tools
2. Getting Started with Tools
3. Hands-on Tool Examples
4. Building Your Own Tools
5. Advanced Tool Use Cases: Email and Meeting Assistant
6. Safe and Responsible Use of Tools
7. Conclusion

**Données non collectées :** Le contenu technique complet (code, exemples, patterns) n'a pas pu être extrait en raison du paywall et du 404 sur le blog personnel.

## 10.2 Article Medium — "Optimize Open WebUI: Three practical extensions"

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Titre | Optimize Open WebUI: Three practical extensions for a better user experience | https://medium.com/pythoneers/optimize-open-webui-three-practical-extensions-for-a-better-user-experience-cbe365af60b1 | Date non collectée |
| Auteur | Stefan Pietrusky | https://medium.com/pythoneers/optimize-open-webui-three-practical-extensions-for-a-better-user-experience-cbe365af60b1 | Date non collectée |

### Contenu détaillé — Pattern Filter :
```python
class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Priority level")
    
    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Pré-traitement avant LLM
        return body
    
    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Post-traitement de la sortie modèle
        return body
```

Cas d'usage démontré : filtre de mots qui remplace les termes indésirables par `[filtered]` via regex pattern matching dans inlet et outlet.

### Contenu détaillé — Pattern Tool avec Event Emitters :
```python
import asyncio

class Tools:
    async def run(self, prompt: str, __user__: dict, 
                  __event_emitter__=None) -> str:
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {"description": "Processing...", "done": False}
            })
        # Logique de traitement
        return result
```

L'exemple boucle sur 5 itérations en émettant un status à chaque étape.

### Contenu détaillé — Pattern Action (sauvegarde de fichier) :
```python
async def action(self, body: dict, __user__=None, 
                __event_emitter__=None, __event_call__=None) -> Optional[dict]:
    response = await __event_call__({
        "type": "input",
        "data": {"title": "message", "placeholder": "enter text"}
    })
```

Cas d'usage : sauvegarder les sorties LLM dans des fichiers en accédant au dernier message assistant via `body["messages"][-1]` et en écrivant dans `/app/data`.

### Contenu détaillé — Configuration Docker pour la persistance :
```bash
docker run -d -p 3000:8080 --gpus all \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --mount type=bind,source="<local_path>",target=/app/data \
  --name open-webui ghcr.io/open-webui/open-webui:cuda
```

Le bind mount "enables data exchange between isolated container and host system" — nécessaire pour que les extensions persistent des fichiers localement.

### Contenu détaillé — Méthodes de déploiement :
1. **Éditeur de code direct** : copier le Python dans le workspace Open WebUI
2. **Marketplace communautaire** : importer depuis `openwebui.com/t/<username>` ou `openwebui.com/f/<username>`
3. **Fichiers JSON** : convertir .py en format .json pour upload

**Source :** https://medium.com/pythoneers/optimize-open-webui-three-practical-extensions-for-a-better-user-experience-cbe365af60b1 — consultée le 13/04/2026

---

# SOURCE 11 : DISCORD OPEN WEBUI

| Donnée | Valeur | URL source | Date source |
|--------|--------|------------|-------------|
| Statut | NON COLLECTÉ — Discord nécessite une authentification et les messages sont éphémères/non indexables via WebFetch | https://discord.com/invite/5rJgQTnV4s | N/A |

**Justification :** Le Discord Open WebUI est un canal de discussion en temps réel qui ne peut pas être accédé programmatiquement sans authentification. Les informations Discord pertinentes ont été partiellement capturées via les issues et discussions GitHub qui y font référence. Pour le corpus, les données Discord ne peuvent être collectées de manière systématique et reproductible.

---

# SYNTHÈSE DES BUGS ET LIMITES CONNUS (consolidation Source 8)

## Bugs résolus (pour contexte historique)

| Bug | Version | Impact | Résolution | Issue |
|-----|---------|--------|------------|-------|
| `__event_emitter__` cassé dans outlet | v0.5.2 | Pas d'émission d'événements depuis les filtres outlet | PR #8159 | #8168 |
| `__event_emitter__` cassé dans Actions | ~v0.5.x | Exception `user_id` dans les Actions | PR #8246 | #8292 |
| Caractères corrompus dans status | v0.5.0+ | Descriptions de status illisibles | Non documenté | #8129 |
| Contenu outlet non persisté | v0.5.2 | Modifications outlet annulées | PR #8159 | #8168 |

## Limitations connues (actuelles ou non résolues)

| Limitation | Impact | Contournement | Source |
|------------|--------|---------------|--------|
| Type hints limités à `str`, `int`, `float`, `bool` dans les Tools | `KeyError: 'type'` avec types complexes | Simplifier toutes les signatures aux 4 primitifs | Discussion #13174 |
| Async tools exposent données sensibles via `functools.partial` | Clés API, mots de passe visibles dans les logs de pipe | Filtrer manuellement les données avant envoi externe | Issue #16307 |
| Native tool calling peu fiable avec petits modèles | Modèle ne traite pas le résultat du tool | Utiliser modèles frontier ou mode Default | Issue #9414 |
| Citations multiples fusionnées | Citations distinctes agrégées en une seule | Utiliser des IDs vraiment distincts (mécanisme de groupement non clarifié) | Issue #17366 |
| Event emitter/call indisponible pour outils externes (OpenAPI/MCP) | Pas de feedback temps réel depuis outils externes | Utiliser REST endpoint `/api/v1/chats/{chat_id}/messages/{message_id}/event` | Issue #20892 |
| Duplication system prompt lors des tool calls agentic | Gaspillage de tokens, surcoût cache | Non documenté | Issue #19169 |
| `outlet()` non appelé pour requêtes API directes | Pas de post-traitement pour clients API | Appeler manuellement `POST /api/chat/completed` | Doc officielle (Filter) |
| Message events cassés en mode Native | `message`, `replace`, `chat:message:delta` écrasés par les snapshots | Utiliser uniquement `status`, `citation`, `notification` en mode Native | Doc officielle (Tools dev) |

## Demandes de fonctionnalités révélant les limites

| Feature request | Implication | Source |
|-----------------|-------------|--------|
| Support SSE pour status events des serveurs agentic | Les serveurs externes ne peuvent pas mettre à jour le status nativement | Issue #19250 |
| Simplification de l'écosystème Tools/Functions | Confusion taxonomique reconnue par la communauté | Discussion #16415 |
| Tâches planifiées en arrière-plan | Pas de support natif pour les fonctions programmées | Discussion #15832 |
| MCP natif avec gestion des tools | Intégration MCP encore en évolution | Discussion #16238 |

---

# DONNÉES NON TROUVÉES (Lot 3)

| Donnée recherchée | Statut | Commentaire |
|--------------------|--------|-------------|
| Discord Open WebUI | Inaccessible | Requiert authentification, contenu éphémère non indexable |
| Article Medium "Beyond Text" (contenu complet) | Paywall | Seuls métadonnées et sommaire collectés. Blog personnel en 404. |
| Issue #11750 (détails) | Collecte superficielle | Titre connu, détails techniques non extraits en profondeur |
| Changelog complet des releases récentes | Non collecté | Le Lot 1 a identifié v0.8.12 mais le changelog détaillé des versions intermédiaires n'a pas été systématiquement parcouru |
| Contenu des scaffolds pipelines (code source) | Structure identifiée | Les 4 fichiers scaffold identifiés mais leur code source n'a pas été extrait |

---

*Fin du Lot 3 — Sources 8 à 11*
*Prêt pour la consolidation finale*