<!-- Généré par scripts/sync-clients.py depuis le dépôt supergeoff/agents (INSTRUCTIONS.md, section socle:memory). Ne pas modifier ici : modifier la source, puis relancer le script. -->

# Mémoire Hindsight (obligatoire)

Le broker relie chaque utilisateur à sa propre banque Hindsight, donc les outils Hindsight ne
prennent aucun identifiant de banque.

Lecture. Avant toute tâche de fond (analyse, rédaction, décision, code, architecture) :

1. Liste les mental models (list_mental_models) une fois par conversation. Chaque mental model
   correspond à un domaine, et son identifiant est le nom du domaine.
2. Si la banque contient un mental model preferences, lis-le (get_mental_model) une fois par
   conversation. Il décrit comment travailler pour l'utilisateur.
3. Choisis le domaine de la demande d'après l'identifiant et le nom des mental models, puis lis
   le mental model de ce domaine. En cas de doute entre deux domaines, lis les deux et retiens
   celui dont la question source couvre la demande.
4. Fais un recall avec le tag du domaine (tags ["d:<domaine>"]), tags_match "any_strict" et
   budget "mid". Ne suppose jamais qu'une information manque sans avoir interrogé Hindsight. Si
   Hindsight ne répond pas, dis-le en une phrase et poursuis.

Écriture. Après chaque échange qui contient un fait marquant, une décision, une préférence
durable ou un recadrage de la part de l'utilisateur, appelle retain (ou sync_retain si une
confirmation immédiate est nécessaire). La persistance passe forcément par l'appel d'outil.
Chaque retain porte exactement deux tags. Le premier prend la forme d:<domaine>, où <domaine>
est l'identifiant d'un mental model existant. N'invente jamais de domaine. Le second prend la
forme s:<sujet>, où <sujet> est tiré du contenu et s'écrit en un à trois mots minuscules sans
accents reliés par des tirets, sans date ni nom de personne. Avant de créer un sujet, liste ceux
qui existent (list_tags avec q "s:*", en paginant jusqu'au total renvoyé) et réutilise celui
qui correspond. Un échange qui touche deux domaines donne deux retains. Renseigne context (une
ligne sur le sujet de l'échange) et timestamp (la date réelle de l'échange, au format
ISO 8601). Si tu ne connais pas la date du jour, obtiens-la avant d'écrire. Les dates ne vont
jamais dans les tags. Un retain ne contient jamais de secret. N'appelle un outil Hindsight qui
supprime ou invalide des données que sur demande explicite de l'utilisateur.

Si la banque n'a encore aucun mental model, fais le recall sans tag de domaine et écris des
retains qui ne portent que le tag de sujet.

Hindsight garde la mémoire de l'utilisateur, pas celle d'un code source : la connaissance d'un
dépôt vit dans le dépôt et dans les outils d'analyse de code.
