<!-- Généré par scripts/sync-clients.py depuis le dépôt supergeoff/agents (INSTRUCTIONS.md, section socle:broker). Ne pas modifier ici : modifier la source, puis relancer le script. -->

# Outils et broker MCP

Les serveurs MCP distants de l'utilisateur passent par un broker unique, qui expose trois
outils : search_tools, call_tool et call_tool_write. Tous les serveurs distants (documentation,
recherche et extraction web, navigateur, GitHub, déploiement, tâches, bases de données, mémoire
de l'utilisateur) s'atteignent par eux, et un outil amont appelé directement échoue avec
« Unknown tool ». Si un outil cité dans ces instructions ou dans un skill n'apparaît pas
directement dans ta liste, cherche-le avec search_tools.

Le déroulé est toujours le même :

1. Appelle search_tools(query, server?, limit?). query est obligatoire et peut être vide,
   server vise un serveur par son identifiant exact (par exemple github) et limit va de 1 à 20
   (8 par défaut). Une query vide avec un server liste les outils de ce serveur, 20 au plus et
   sans pagination. La réponse est du JSON dans un élément texte, qu'il faut lire : chaque
   outil porte name, server, read_only, run_with, description et input_schema, et la réponse
   peut contenir hint et unavailable_servers.
2. Lance l'outil avec celui que run_with désigne : call_tool pour lire, call_tool_write pour
   écrire. call_tool_write sert aux actions que l'utilisateur demande et à celles que ces
   instructions imposent, comme les retain Hindsight et les extractions crawl4ai. Il exécute
   aussi les outils destructeurs et le broker ne demande jamais de confirmation : ne t'en sers
   jamais pour contourner un refus.
3. Passe name exactement comme il est renvoyé, avec son préfixe de serveur (par exemple
   searxng-web_search), sans le raccourcir ni le deviner, et place les paramètres de l'outil
   dans arguments, conformément à input_schema.

La découverte remplace toute supposition. Les serveurs visibles dépendent de la personne et
changent avec le temps : ne suppose jamais qu'un serveur ou un outil existe, et ne fige aucun
nom ni aucun schéma. Avant une tâche qui peut demander un outil externe, appelle search_tools,
dont la description se termine par « Your servers: … ». search_tools renvoie toujours jusqu'à
limit résultats, liés ou non à la demande : juge-les sur leur nom et leur description. Pour une
source qui a un outil (GitHub, Coder, Google, Dokploy…), passe d'abord par l'outil et cherche-le
avant de conclure qu'il manque. Pour la documentation d'une bibliothèque ou d'un framework,
cherche un outil de documentation avant de te fier à ce que tu sais. Si aucun outil ne répond et
qu'une API existe (YouTube, X…), demande un jeton à l'utilisateur en lui indiquant où
l'enregistrer : le tableau de bord du broker pour un serveur MCP, son gestionnaire de secrets
pour une clé d'API. Ne demande jamais à l'utilisateur de coller un secret dans la conversation.
Le web public et l'accès direct sans compte viennent en dernier recours.

En cas d'échec :

- Lis isError dans chaque réponse, car les résultats amont reviennent tels quels.
- « Unknown tool <name> » peut signifier que le serveur n'est pas prêt pour cette personne ou
  que le catalogue est périmé : relance search_tools au lieu de réessayer le nom. Après toute
  erreur, cherche de nouveau.
- Un serveur absent de « Your servers », ou présent dans unavailable_servers, existe peut-être
  quand même. Dis à l'utilisateur lequel manque, car lui seul peut le connecter (OAuth sur la
  page /ui/connect de LiteLLM), enregistrer son secret sur le tableau de bord du broker
  (https://mcp.supergeoff.top/) ou ouvrir ce tableau de bord une fois pour créer sa clé
  LiteLLM, ce qu'une réponse de search_tools en texte brut signale. Les catalogues sont en
  cache : cherche de nouveau ensuite. Un 401 persistant signifie que le client doit se
  reconnecter au broker.
- La limite est de 120 requêtes par minute et par personne, partagée entre tous ses clients.
  Sur un 429 ou « Too many MCP requests », attends environ une minute, sans boucle de nouvelles
  tentatives ni rafale d'appels en parallèle. Après un lot refusé en partie, vérifie quels
  appels sont passés avant de rejouer une écriture. Un appel peut durer jusqu'à deux minutes :
  ne renvoie pas une écriture avant ce délai.
