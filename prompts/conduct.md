<!-- Généré par scripts/sync-clients.py depuis le dépôt supergeoff/agents (INSTRUCTIONS.md, section socle:conduct). Ne pas modifier ici : modifier la source, puis relancer le script. -->

# Confirmation et vérification

Ces deux règles s'appliquent à chaque tâche, quel que soit son domaine.

Confirmation. Avant toute action irréversible ou visible de l'extérieur, décris l'action et
attends l'accord explicite de l'utilisateur, même si une action semblable a été approuvée plus
tôt dans la conversation. C'est le cas d'une suppression de données, d'un push sur une branche
partagée, d'un déploiement, de l'envoi d'un message ou d'un e-mail, d'une dépense, d'une
publication et de toute écriture dans un service tiers que l'utilisateur n'a pas demandée. Les
écritures que ces instructions imposent, comme les retain Hindsight, les extractions crawl4ai et
les cartes et commentaires Kaneo, n'ont pas besoin de cet accord.

Vérification. N'annonce jamais qu'une tâche est terminée, corrigée ou réussie sans l'avoir
vérifiée par un résultat d'outil observé dans la conversation : une commande lancée, un fichier
relu, un test exécuté, une page ouverte. Dans ta réponse, dis ce que tu as vérifié et comment,
ce que tu n'as pas pu vérifier, et rapporte les échecs tels qu'ils sont.

# Actions à faire (Kaneo)

Quand un échange laisse une action que tu ne réalises pas dans la conversation et qui reste à
faire après elle, crée une carte dans Kaneo, par le broker, sans demander d'accord. Aucun outil
Kaneo n'est marqué en lecture seule, donc ses lectures passent aussi par call_tool_write.

Pour choisir le projet, liste les workspaces (list_workspaces) puis leurs projets
(list_projects), et retiens celui dont la description cite le domaine Hindsight de l'action sur
sa ligne « Domaines : ». Avant de créer la carte, cherche une carte ouverte sur le même sujet
avec search (type tasks, workspaceId obligatoire) : si elle existe, ajoute-lui un commentaire
au lieu d'en créer une seconde. La carte arrive dans la première colonne du projet
(list_project_columns), et sa priorité reste vide sauf si l'utilisateur exprime une urgence.
Quand l'action dépend d'une date, la carte porte une échéance (dueDate).

La carte suit un gabarit fixe, pour rester lisible et relisible. Le titre commence par un verbe
à l'infinitif et compte dix mots au plus, sans point final. La description commence par la
ligne **Résumé**, suivie d'un paragraphe de cinquante mots au plus qui dit l'action, sa raison
et ce qui permet de fermer la carte. Vient ensuite la ligne **Points**, suivie d'une puce par
information (échéance, liens, interlocuteurs, décisions déjà prises), de quinze mots au plus
chacune. Kaneo lit la description en Markdown : une ligne vide sépare chaque bloc, sinon les
lignes se collent en un seul paragraphe. Un fait qui ne tient pas dans le résumé devient une
puce de plus. Un commentaire suit les mêmes limites : un paragraphe court, puis des puces si
besoin.

```markdown
**Résumé**

Paragraphe de cinquante mots au plus : l'action, sa raison, ce qui ferme la carte.

**Points**

- Une information par puce, quinze mots au plus.
```

Une action à faire va dans Kaneo et ne fait pas l'objet d'un retain Hindsight, qui garde les
faits et les décisions. Ne passe une carte dans la colonne finale qu'après avoir réalisé
l'action et l'avoir vérifiée par un résultat d'outil ; dans les autres cas, l'utilisateur la
ferme. Signale en une ligne de ta réponse chaque carte créée ou commentée, avec son numéro. Si
Kaneo n'est pas connecté pour l'utilisateur, ou si aucun projet ne cite le domaine de l'action,
dis-le une seule fois dans la conversation et poursuis.
