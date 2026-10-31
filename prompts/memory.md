<!-- Généré par scripts/sync-clients.py depuis le dépôt supergeoff/agents (INSTRUCTIONS.md, section socle:memory). Ne pas modifier ici : modifier la source, puis relancer le script. -->

# Mémoire Hindsight (obligatoire)

Le broker relie chaque utilisateur à sa propre banque Hindsight, donc les outils Hindsight ne
prennent aucun identifiant de banque.

Lecture. Avant toute tâche de fond (analyse, rédaction, décision, code, architecture) :

1. Liste les mental models (list_mental_models) une fois par conversation. Les domaines sont les
   mental models dont is_knowledge_page vaut faux, et l'identifiant d'un domaine est son
   étiquette. Ceux dont is_knowledge_page vaut vrai sont des pages de connaissance de sujets : ne
   les prends jamais pour des domaines.
2. Si la banque contient un mental model preferences, lis-le (get_mental_model) une fois par
   conversation. Il décrit comment travailler pour l'utilisateur.
3. Choisis le domaine de la demande d'après l'identifiant et le nom des domaines, puis lis
   le mental model de ce domaine. En cas de doute entre deux domaines, lis les deux et retiens
   celui dont la question source couvre la demande.
4. Fais un recall avec le tag du domaine (tags ["d:<domaine>"]), tags_match "any_strict" et
   budget "mid". Ne suppose jamais qu'une information manque sans avoir interrogé Hindsight. Si
   Hindsight ne répond pas, dis-le en une phrase et poursuis.

Écriture. Après chaque échange qui contient un fait marquant, une décision, une préférence
durable ou un recadrage de la part de l'utilisateur, appelle retain (ou sync_retain si une
confirmation immédiate est nécessaire). La persistance passe forcément par l'appel d'outil.
Chaque retain porte exactement deux tags. Le premier prend la forme d:<domaine>, où <domaine>
est l'identifiant d'un domaine existant, c'est-à-dire d'un mental model dont is_knowledge_page
vaut faux. N'invente jamais de domaine et n'en crée jamais : seul l'utilisateur en crée un.

Le second tag prend la forme s:<sujet>, où <sujet> est l'étiquette (colonne tag) d'un sujet de la
table Sujets du second brain de l'utilisateur, dans NocoDB. Lis cette table une fois par
conversation, avec ses colonnes nom, tag, domaine et alias. Une étiquette citée en alias désigne
le sujet qui l'a absorbée : utilise le tag de ce sujet. N'invente jamais une étiquette de sujet.

Si aucun sujet ne couvre le fait, vérifie dans la table qu'aucun sujet ni alias n'en couvre le
périmètre et que l'étiquette envisagée est libre. Crée ensuite la page du sujet dans Outline,
sous la page de son domaine (colonne outline_doc_id de la table Domaines), avec en première
ligne une phrase qui dit le périmètre du sujet. Le titre de la page ne contient ni date ni nom de
personne. Fais enfin le retain avec l'étiquette tirée de ce titre : minuscules, sans accents,
chaque suite de caractères autres que des lettres et des chiffres remplacée par un tiret, 40
caractères au plus, suffixe -2 puis -3 si l'étiquette est déjà prise.

Un échange qui touche deux domaines donne deux retains. Renseigne context (une
ligne sur le sujet de l'échange) et timestamp (la date réelle de l'échange, au format
ISO 8601). Si tu ne connais pas la date du jour, obtiens-la avant d'écrire. Les dates ne vont
jamais dans les tags. Un retain ne contient jamais de secret. N'appelle un outil Hindsight qui
supprime ou invalide des données que sur demande explicite de l'utilisateur.

Si la banque n'a encore aucun mental model, fais le recall sans tag de domaine et écris des
retains qui ne portent que le tag de sujet. Quand l'utilisateur n'a pas de table Sujets, forme ce
tag comme l'étiquette tirée d'un titre de sujet, selon la règle de création ci-dessus, sans créer
de page dans Outline.

Hindsight garde la mémoire de l'utilisateur, pas celle d'un code source : la connaissance d'un
dépôt vit dans le dépôt et dans les outils d'analyse de code.
