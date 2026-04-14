# Rich UI Embedding

Le Rich UI Embedding permet d'afficher du contenu HTML interactif dans l'interface de chat via `HTMLResponse` avec un header `Content-Disposition: inline`. Le contenu est rendu dans un iframe sandboxé.

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ — consultée le 13/04/2026

## Disponibilité

| Type | Rich UI supporté |
|------|-----------------|
| Tools | ✅ |
| Actions | ✅ |
| Pipes | ❌ |
| Filters | ❌ |

## Position de rendu

- **Tools :** inline au tool call indicator
- **Actions :** au-dessus du texte du message

## Implémentation Tool

```python
from fastapi.responses import HTMLResponse

def create_visualization_tool(self, data: str) -> HTMLResponse:
    html_content = """<!DOCTYPE html><html>...</html>"""
    headers = {"Content-Disposition": "inline"}
    return HTMLResponse(content=html_content, headers=headers)
```

## Fournir du contexte au LLM (tuple)

Par défaut, sans contexte custom, le LLM reçoit : "Tool name: Embedded UI result is active and visible to the user."

Pour fournir un contexte personnalisé au LLM :

```python
def create_chart(self, data: str) -> tuple:
    html_content = "<html>...</html>"
    headers = {"Content-Disposition": "inline"}
    result_context = {"status": "success", "chart_type": "scatter", "data_points": 42}
    return HTMLResponse(content=html_content, headers=headers), result_context
```

## Gestion hauteur iframe

L'iframe ne connaît pas sa propre hauteur. Deux approches :

### Via postMessage (recommandé quand allowSameOrigin est OFF)

```javascript
function reportHeight() {
    const h = document.documentElement.scrollHeight;
    parent.postMessage({ type: 'iframe:height', height: h }, '*');
}
window.addEventListener('load', reportHeight);
new ResizeObserver(reportHeight).observe(document.body);
```

### Auto-resize (allowSameOrigin ON)

Quand `allowSameOrigin` est activé, l'iframe peut communiquer directement avec le parent et s'auto-resize.

## Sandbox

### Flags toujours actifs

- `allow-scripts` — Exécution JavaScript
- `allow-popups` — window.open()
- `allow-downloads` — Téléchargements

### Flags configurables par l'utilisateur (Settings → Interface)

- **"Allow Iframe Same-Origin Access"** — allowSameOrigin
- **"Allow Iframe Form Submissions"** — allowForms

### allowSameOrigin OFF (défaut)

- Isolation complète
- L'iframe ne peut pas accéder aux cookies/localStorage/DOM du parent
- Requiert `postMessage` pour reporter la hauteur
- Configuration la plus sûre

### allowSameOrigin ON

- L'iframe accède au contexte parent
- Auto-resize sans script supplémentaire
- Chart.js et Alpine.js **auto-injectés** si détectés dans le contenu HTML
- Nécessite confiance dans le contenu embarqué

## Communication avancée

### Injection d'arguments (`window.args`)

Les Tools injectent automatiquement les paramètres dans `window.args`. Les Actions ne reçoivent PAS `window.args`.

```javascript
window.addEventListener('load', () => {
    const args = window.args; // Paramètres JSON passés au tool
});
```

### Soumission de prompt

| Type | Comportement |
|------|-------------|
| `input:prompt` | Remplit l'input sans soumettre |
| `input:prompt:submit` | Remplit et soumet |
| `action:submit` | Soumet le texte d'input courant |

```javascript
parent.postMessage({ type: 'input:prompt:submit', text: 'Show summary' }, '*');
```

Quand `allowSameOrigin` est OFF, `input:prompt:submit` affiche un dialogue de confirmation.

## Rich UI vs Execute Event

| Aspect | Rich UI Embed | Execute Event |
|--------|---------------|---------------|
| Environnement | Iframe sandboxé | Page principale (non sandboxé) |
| Persistance | Sauvegardé dans l'historique | Éphémère, perdu au rechargement |
| Accès page | Isolé par défaut | Accès complet DOM/cookies/storage |
| Formulaires | Requiert allowForms | Toujours fonctionnel |
| Meilleur usage | Dashboards persistants, graphiques | Interactions transitoires, téléchargements |

## Comportement au rechargement

Quand un chat historique est rechargé, le contenu HTML du Rich UI embed est **re-rendu depuis le contenu sauvegardé en BDD** (dans les embeds du message). L'iframe est recréé avec le même HTML. Il n'y a pas de mise en cache spécifique — chaque rechargement reconstruit l'iframe à partir des données persistées.

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/rich-ui/ — consultée le 13/04/2026
