# Plan methodologique -- Corpus documentaire sur la creation d'outils custom pour Open WebUI

---

## 1. Sources a consulter imperativement

Classees de la plus fiable a la moins fiable.

**Source 1 -- Documentation officielle Open WebUI**
URL : https://docs.openwebui.com/features/extensibility/plugin/
Ce qu'on y cherche : architecture du systeme de plugins (Tools, Functions, Pipes, Filters, Actions), signatures des methodes, parametres disponibles (`__event_emitter__`, `__event_call__`, `__user__`, Valves), cycle de vie d'un outil custom.
Limites : la documentation evolue rapidement au fil des releases ; certaines sections peuvent etre en retard par rapport au code reel. Verifier systematiquement la correspondance avec la version deployee.

**Source 2 -- Code source du depot principal (GitHub open-webui/open-webui)**
URL : https://github.com/open-webui/open-webui
Ce qu'on y cherche : implementation reelle du moteur d'execution des fonctions, mecanisme `exec`, gestion des Valves, EventEmitter, schema de la base de donnees pour le stockage des fonctions. Lectures prioritaires : dossiers backend relatifs aux plugins et au routage des fonctions.
Limites : le code peut contenir de la dette technique (coexistence Peewee / SQLAlchemy signale par la communaute). Ne pas confondre code legacy et code actif.

**Source 3 -- Documentation officielle des Events et du developpement de plugins**
URL : https://docs.openwebui.com/features/plugin/development/events/
Ce qu'on y cherche : types d'evenements (Status, Message), syntaxe de `__event_emitter__` et `__event_call__`, mecanismes de communication bidirectionnelle pour les modales et confirmations utilisateur.
Limites : memes reserves que la source 1 sur la fraicheur. Les exemples peuvent ne pas couvrir tous les cas limites.

**Source 4 -- Pages specifiques de la doc : Pipe Function, Action Function, Filter Function**
URL Pipe : https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/
URL Action : https://docs.openwebui.com/features/extensibility/plugin/functions/action/
URL Filter : https://docs.openwebui.com/features/extensibility/plugin/functions/filter/ (a verifier)
Ce qu'on y cherche : la specification de chaque type de fonction, ses parametres d'entree/sortie, ses contraintes, et des exemples minimaux.
Limites : chaque page documente un seul type ; la vue d'ensemble transversale n'est pas toujours explicite.

**Source 5 -- Depot GitHub open-webui/docs**
URL : https://github.com/open-webui/docs
Ce qu'on y cherche : les sources Markdown de la documentation, y compris les modifications recentes non encore deployees sur le site. Permet de reperer des sections en cours de redaction ou recemment modifiees.
Limites : depot de documentation, pas de code executif. Peut contenir des brouillons incomplets.

**Source 6 -- DeepWiki : Functions System Overview**
URL : https://deepwiki.com/open-webui/docs/4.2-functions-system
Ce qu'on y cherche : une vue d'architecture generee a partir du code source, utile comme complement a la documentation officielle pour comprendre les dependances internes.
Limites : source generee automatiquement (probablement par IA). Peut contenir des interpretations erronees. A recouper systematiquement avec le code source.

**Source 7 -- Bibliotheque communautaire Open WebUI**
URL : https://openwebui.com/functions
Ce qu'on y cherche : des exemples concrets et diversifies de fonctions publiees par la communaute. Patterns recurrents, conventions de nommage, usage des Valves dans des cas reels, exemples d'Actions avec interface.
Limites : code communautaire de qualite tres variable. Aucune garantie de conformite aux bonnes pratiques. Certaines fonctions peuvent etre obsoletes ou incompatibles avec les versions recentes. Ne jamais utiliser comme reference normative.

**Source 8 -- Discussions GitHub (Issues et Discussions)**
URL : https://github.com/open-webui/open-webui/discussions et /issues
Ce qu'on y cherche : problemes connus lies a `__event_emitter__`, bugs documentes sur les Actions, retours d'experience des developpeurs, demandes de fonctionnalites revelant les limites actuelles.
Limites : informations dispersees, non structurees, parfois contradictoires. Les issues fermees peuvent concerner des versions obsoletes.

**Source 9 -- Depot communautaire open-webui-tool-skeleton**
URL : https://github.com/pahautelman/open-webui-tool-skeleton
Ce qu'on y cherche : un template de depart pour la creation d'outils, avec structure de fichier, bonnes pratiques suggerees, et exemples annotes.
Limites : depot tiers, potentiellement non maintenu. Verifier la date du dernier commit et la compatibilite avec la version courante d'Open WebUI.

**Source 10 -- Articles Medium / blogs techniques**
URL exemple : https://medium.com/@hautel.alex2000/beyond-text-equipping-your-open-webui-ai-with-action-tools-594e15cd7903
Ce qu'on y cherche : tutoriels pas-a-pas, retours d'experience narratifs, cas d'usage concrets (notamment sur les Actions et les interfaces interactives).
Limites : contenu editorial, non maintenu, qui peut devenir obsolete rapidement. Qualite et exactitude variables. A utiliser comme complement illustratif, jamais comme reference technique primaire.

**Source 11 -- Discord Open WebUI**
URL : https://discord.com/invite/5rJgQTnV4s
Ce qu'on y cherche : retours informels des developpeurs et utilisateurs avances, solutions a des problemes non documentes, annonces de changements en amont des releases.
Limites : contenu ephemere, non indexe, difficile a citer. Les informations peuvent etre incorrectes ou perimees. Fiabilite la plus basse de cette liste.

---

## 2. Questions cles auxquelles le corpus devra repondre

Classees par importance structurante (de la plus fondamentale a la plus operationnelle).

1. **Quelle est la taxonomie complete des types d'extensions dans Open WebUI, et quelles sont les frontieres fonctionnelles entre Tools, Functions (Pipe, Filter, Action) et Pipelines ?**
   Justification : sans cette cartographie, aucune decision de conception n'est possible.

2. **Quel est le cycle de vie complet d'une fonction custom, de sa creation a son execution par l'utilisateur final ?**
   Justification : comprendre le mecanisme d'enregistrement, de chargement et d'execution (y compris le recours a `exec`) est un prealable a tout developpement.

3. **Quels sont les parametres injectes automatiquement dans chaque type de fonction (`__event_emitter__`, `__event_call__`, `__user__`, `__model__`, `__request__`, body, Valves) et quel est leur role exact ?**
   Justification : ces parametres constituent l'API implicite du systeme de plugins.

4. **Comment fonctionne le systeme de Valves et comment l'utiliser pour rendre un outil configurable sans modification de code ?**
   Justification : les Valves sont le mecanisme central de parametrage ; mal les comprendre conduit a du code rigide et non reutilisable.

5. **Comment creer une interface d'interaction utilisateur (modale, confirmation, saisie) via `__event_call__` et les evenements associes ?**
   Justification : question directement liee a l'objectif du corpus (outils avec interface interactive).

6. **Quelles sont les contraintes de securite et d'isolation liees a l'execution de code arbitraire sur le serveur ?**
   Justification : toute documentation sur la creation d'outils qui ignore la securite est dangereusement incomplete.

7. **Quelle est la difference concrete entre une Function executee dans le processus Open WebUI et une Pipeline executee sur un serveur separe, et quand choisir l'une plutot que l'autre ?**
   Justification : choix architectural fondamental qui determine les capacites disponibles (import de packages, isolation, performances).

8. **Comment un Pipe peut-il se presenter comme un modele autonome dans l'interface, et quelles sont les implications pour le routage des requetes ?**
   Justification : les Pipes qui apparaissent comme des modeles sont un cas d'usage puissant mais potentiellement deroutant.

9. **Quels sont les patterns d'erreur les plus frequents lors du developpement d'outils custom, et comment les diagnostiquer ?**
   Justification : question operationnelle essentielle pour un corpus a vocation pratique.

10. **Comment tester, deboguer et iterer sur un outil custom sans redemarrer l'instance complete ?**
    Justification : l'experience developpeur conditionne l'adoption et la qualite des outils produits.

---

## 3. Plan type du corpus (environ dix sections)

**Section 1 -- Introduction et perimetre**
Contenu : definition de l'objectif du corpus, public cible, version d'Open WebUI couverte, conventions de notation utilisees.
A eviter : promesses de couverture exhaustive, historique du projet non pertinent pour le developpeur.

**Section 2 -- Cartographie du systeme d'extensibilite**
Contenu : schema des differents types d'extensions (Tools, Pipe, Filter, Action, Pipelines), leurs relations, leurs differences. Un tableau comparatif synthetique.
A eviter : entrer dans le detail d'implementation a ce stade ; se limiter a la vue d'ensemble.

**Section 3 -- Architecture technique et cycle de vie**
Contenu : comment Open WebUI charge, enregistre et execute les fonctions. Mecanisme `exec`, injection de dependances, flux de donnees du message utilisateur a la reponse.
A eviter : reproduire le code source in extenso. Privilegier des schemas de flux.

**Section 4 -- L'API implicite : parametres injectes et Valves**
Contenu : reference complete des parametres disponibles pour chaque type de fonction. Documentation des Valves avec exemples de configuration.
A eviter : lister des parametres sans expliquer leur contexte d'utilisation. Chaque parametre doit etre illustre.

**Section 5 -- Creer un Tool (outil appele par le LLM)**
Contenu : anatomie d'un Tool, signature attendue, interaction avec le modele, exemples progressifs (du plus simple au plus complet).
A eviter : confondre Tool et Function/Pipe. Ne pas presupposer que le lecteur connait le function calling OpenAI.

**Section 6 -- Creer un Pipe (modele/agent custom)**
Contenu : structure d'un Pipe, comment il se manifeste comme un modele dans l'interface, appel a des API externes, orchestration multi-LLM.
A eviter : traiter les Pipes comme de simples proxys ; montrer leur potentiel d'orchestration.

**Section 7 -- Creer un Filter (pre/post-traitement)**
Contenu : methodes Inlet et Outlet, cas d'usage (moderation, enrichissement, traduction), interaction avec le flux de messages.
A eviter : negliger les effets de bord d'un Filter mal concu sur l'experience utilisateur.

**Section 8 -- Creer une Action avec interface interactive**
Contenu : creation de boutons custom dans la barre de messages, usage de `__event_emitter__` (statuts, messages) et `__event_call__` (modales, confirmations, saisies). Exemples concrets d'interfaces interactives.
A eviter : presenter les Actions comme de simples boutons sans expliquer le mecanisme de communication bidirectionnelle.

**Section 9 -- Securite, limites et bonnes pratiques**
Contenu : risques lies a `exec`, gestion des permissions, isolation des Pipelines, recommandations pour la revue de code, limites connues du systeme (absence d'import de packages pour les Functions internes, par exemple).
A eviter : minimiser les risques de securite ou les presenter comme des details mineurs.

**Section 10 -- Developpement, test et debogage**
Contenu : workflow de developpement recommande, outils de diagnostic, gestion des erreurs, strategie de test, conseils pour l'iteration rapide.
A eviter : presupposer un environnement de developpement specifique sans le justifier.

---

## 4. Pieges classiques d'un tel corpus

**Piege 1 -- Confondre les types d'extensions.** Tools, Functions, Pipes, Filters, Actions et Pipelines ont des noms proches et des perimetres qui se chevauchent partiellement. Un corpus qui ne clarifie pas rigoureusement la taxonomie des le depart engendrera de la confusion a chaque section suivante.

**Piege 2 -- Documenter une version sans le dire.** Open WebUI evolue tres rapidement. Un corpus qui ne mentionne pas explicitement la version documentee deviendra trompeur en quelques mois. Chaque affirmation technique devrait pouvoir etre rattachee a un commit ou une release.

**Piege 3 -- Se fier uniquement a la documentation officielle.** La doc peut etre en retard sur le code. Inversement, se fier uniquement au code sans lire la doc conduit a documenter des details d'implementation instables. Le recoupement des deux est obligatoire.

**Piege 4 -- Traiter le code communautaire comme reference.** La bibliotheque communautaire contient des exemples utiles mais de qualite tres inegale. Presenter un exemple communautaire comme un patron de conception sans l'avoir valide contre la documentation et le code source est une erreur methodologique.

**Piege 5 -- Sous-estimer l'aspect securite.** Le systeme execute du code Python arbitraire via `exec`. Un corpus qui presente la creation d'outils sans aborder ce point frontalement expose ses lecteurs a des risques reels.

**Piege 6 -- Ignorer la distinction Function interne / Pipeline externe.** Les Functions internes ne peuvent pas importer de packages supplementaires ; les Pipelines le peuvent mais s'executent sur un serveur separe. Confondre les deux conduit a des recommandations inapplicables.

**Piege 7 -- Presenter les modales et interfaces interactives comme des fonctionnalites simples.** Le mecanisme `__event_call__` pour la communication bidirectionnelle est puissant mais peu documente. Sous-estimer sa complexite ou ses limites produit des sections frustrantes pour le lecteur.

**Piege 8 -- Produire un corpus trop abstrait ou trop concret.** Trop abstrait : le lecteur ne sait pas quoi ecrire. Trop concret : les exemples deviennent obsoletes rapidement. L'equilibre passe par des exemples minimaux annotes, accompagnes de principes generaux.

**Piege 9 -- Ne pas tester les exemples de code fournis.** Chaque extrait de code presente dans le corpus doit avoir ete execute et valide sur une instance reelle. Les exemples non testes sont la premiere source de perte de credibilite.

**Piege 10 -- Raisonner par analogie avec d'autres systemes de plugins.** Open WebUI a une architecture specifique (injection de parametres, Valves, `exec`). Plaquer les concepts d'un autre systeme de plugins (WordPress, VSCode, etc.) sans verifier leur applicabilite est un raisonnement fallacieux frequent.

---

## 5. Donnees a collecter en amont

Avant de produire le corpus, les elements suivants doivent etre reunis :

- **La version exacte d'Open WebUI ciblee**, avec le hash du commit ou le numero de release correspondant. Toute la documentation en depend.

- **Le code source des fichiers backend relatifs au systeme de plugins**, en particulier les modules qui gerent le chargement, l'enregistrement et l'execution des fonctions. Lire le code, pas seulement la doc.

- **La liste complete des parametres injectes pour chaque type de fonction**, extraite du code source (pas de la documentation seule). Comparer avec la doc pour identifier les ecarts.

- **La specification exacte des evenements emis par `__event_emitter__`** (types, structure du payload, comportement cote frontend) et des appels possibles via `__event_call__` (types de modales, champs disponibles, format de retour).

- **Un echantillon representatif de fonctions communautaires** (au moins trois par type : Tool, Pipe, Filter, Action), selectionnees pour leur diversite et leur qualite, a analyser comme materiau d'illustration.

- **Les issues et discussions GitHub les plus pertinentes** sur les bugs, limitations et demandes d'amelioration du systeme de plugins. Elles revelent les zones fragiles que le corpus doit documenter avec prudence.

- **Le changelog des dernieres releases**, pour identifier les changements recents qui affectent le systeme de plugins et eviter de documenter un comportement deja modifie.

- **Un environnement de test fonctionnel** (instance Open WebUI operationnelle) permettant de valider chaque exemple de code avant inclusion dans le corpus.

- **La documentation du systeme Pipelines** (serveur separe), pour pouvoir tracer clairement la frontiere avec les Functions internes et documenter les deux voies sans les confondre.

- **Les schemas ou descriptions de l'interface frontend** relatifs aux modales, boutons d'Action et affichage des statuts, afin de documenter le rendu cote utilisateur (pas seulement le code serveur).

---

*Ce plan methodologique ne contient aucune donnee factuelle propre a l'objectif. Il constitue un cadre de travail pour la collecte, l'organisation et la production du corpus documentaire.*