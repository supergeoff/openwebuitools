# Système de Valves

Les Valves sont le mécanisme central de configuration dynamique des extensions. Elles héritent de `pydantic.BaseModel` et génèrent automatiquement des champs GUI dans l'interface d'administration.

> Source : https://docs.openwebui.com/features/extensibility/plugin/development/valves — consultée le 13/04/2026

## Valves vs UserValves

| Aspect | Valves | UserValves |
|--------|--------|------------|
| Qui configure | Administrateurs uniquement (Tools/Functions menus) | Tout utilisateur depuis une session de chat |
| Persistance | System-wide, accessibles à toutes les exécutions du plugin | Par utilisateur, stockées dans `user.settings.functions.valves[function_id]` |
| Accès | `self.valves.field_name` | `__user__["valves"].field_name` |
| Cas d'usage | Clés API, URLs de service, configuration globale | Préférences utilisateur, toggles personnels |

## Accès aux Valves — Attention au piège

```python
# CORRECT : accès via attribut
self.valves.api_key
__user__["valves"].preference

# INCORRECT : accès via dictionnaire retourne la valeur par défaut, pas la valeur réelle !
__user__["valves"]["preference"]  # ← VALEUR PAR DÉFAUT, PAS LA VALEUR RÉELLE
```

## Types de champs

### Types de base

```python
from pydantic import BaseModel, Field
from typing import Literal

class Valves(BaseModel):
    # Integer
    test_valve: int = Field(default=4, description="...")

    # Boolean (rendu comme switch dans l'UI)
    test_user_valve: bool = Field(default=False, description="...")

    # String avec choix limités
    choice_option: Literal["choiceA", "choiceB"] = Field(default="choiceA", description="...")
```

### Champ mot de passe (masqué dans l'UI)

```python
service_password: str = Field(
    default="",
    description="Your service password",
    json_schema_extra={"input": {"type": "password"}}
)
```

### Dropdown select statique

```python
log_level: str = Field(
    default="info",
    description="Logging verbosity",
    json_schema_extra={
        "input": {
            "type": "select",
            "options": [
                {"value": "debug", "label": "Debug (Verbose)"},
                {"value": "info", "label": "Info (Standard)"},
                {"value": "warn", "label": "Warning (Minimal)"},
                {"value": "error", "label": "Error (Critical Only)"}
            ]
        }
    }
)
```

### Dropdown select dynamique

Le nom de la méthode (string) est appelé dynamiquement pour peupler les options.

```python
selected_model: str = Field(
    default="",
    description="Choose a model to use",
    json_schema_extra={
        "input": {
            "type": "select",
            "options": "get_model_options"
        }
    }
)

@classmethod
def get_model_options(cls, __user__=None) -> list[dict]:
    # __user__ est injecté automatiquement (comme un reserved arg)
    # quand l'utilisateur ouvre les paramètres, sinon None
    return [
        {"value": "gpt-4", "label": "GPT-4"},
        {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"}
    ]
```

### Champ requis

```python
api_key: str = Field(default="", description="API key", required=True)
```

> **Validation `required=True` :** Côté UI, un champ requis vide affiche un avertissement visuel mais ne bloque pas l'exécution. Côté backend, la validation Pydantic s'applique uniquement si la valeur par défaut est absente — avec `default=""`, un champ vide passe la validation. Pour un vrai blocage, ne pas fournir de valeur par défaut.

## Champ priority

```python
priority: int = Field(default=0, description="Lower values execute first")
```

Les valeurs basses sont exécutées en premier. Ce champ contrôle :

- L'ordre d'exécution des Filters (inlet/outlet)
- L'ordre d'affichage des boutons Action (priority ascending, puis alphabétique par function ID si égalité)

## Exemple complet

```python
from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        api_key: str = Field(default="", description="API key for the service", required=True)
        base_url: str = Field(default="https://api.example.com", description="Service endpoint")
        log_level: str = Field(
            default="info",
            description="Logging verbosity",
            json_schema_extra={
                "input": {
                    "type": "select",
                    "options": [
                        {"value": "debug", "label": "Debug"},
                        {"value": "info", "label": "Info"},
                        {"value": "warn", "label": "Warning"}
                    ]
                }
            }
        )
        priority: int = Field(default=0, description="Execution priority")

    class UserValves(BaseModel):
        show_status: bool = Field(default=True, description="Show status updates")
        max_results: int = Field(default=10, description="Maximum results to return")

    def __init__(self):
        self.valves = self.Valves()
```

## Mécanisme de persistance

### Valves (admin)

Stockées dans la colonne `valves` (JSONField) de la table `function` ou `tool` correspondante. Lecture via `get_function_valves_by_id()` / outil équivalent, écriture via `update_function_valves_by_id()`. Accessibles à toutes les exécutions du plugin.

### UserValves

Stockées dans `user.settings.functions.valves[function_id]` (JSON imbriqué dans les settings utilisateur). Lecture via `get_user_valves_by_id_and_user_id()`. Chaque utilisateur a ses propres valeurs, indépendantes les unes des autres.
