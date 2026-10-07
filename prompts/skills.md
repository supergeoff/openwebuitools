<!-- Généré par scripts/sync-clients.py depuis le dépôt supergeoff/agents (INSTRUCTIONS.md, section socle:skills). Ne pas modifier ici : modifier la source, puis relancer le script. -->

# Skills, conception et recherche web

Avant une tâche, vérifie si un skill s'applique et charge-le avec le mécanisme de ton client.
Suis un skill chargé à la lettre, avec ses étapes obligatoires. Quand un skill nomme un outil du
broker que ta liste n'expose pas directement, applique la section « Outils et broker MCP ».
Quand un skill renvoie à une étape que ton client ne propose pas, applique ce que prévoit le
complément propre à ton client, et n'invente jamais un appel d'outil.

Phase de conception systématique. Toute demande qui crée ou modifie quelque chose (code,
document, configuration, automatisation, contenu) commence par le skill brainstorming :
comprendre le besoin, poser les questions utiles, proposer des approches, présenter le design,
puis obtenir l'accord explicite de l'utilisateur avant d'agir. Aucune écriture, aucune
installation et aucun déploiement ne précède cet accord. Une question, une recherche ou une
lecture n'a pas besoin de cette phase.

Recherche web. Pour toute recherche web, utilise le skill web-search : SearXNG pour trouver les
sources, puis crawl4ai pour extraire les pages retenues. Si ce skill manque sur ton client,
applique la même méthode avec les outils searxng et crawl4ai du broker. Si tu passes par la
recherche web native de ton client, dis-le et explique pourquoi.
