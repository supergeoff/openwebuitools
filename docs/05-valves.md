# Valve System

Valves are the central mechanism for dynamic configuration of extensions. They inherit from `pydantic.BaseModel` and automatically generate GUI fields in the admin interface.

> Source: https://docs.openwebui.com/features/extensibility/plugin/development/valves — consulted 04/13/2026

## Valves vs UserValves

| Aspect | Valves | UserValves |
|--------|--------|------------|
| Who configures | Administrators only (Tools/Functions menus) | Any user from a chat session |
| Persistence | System-wide, accessible to all plugin executions | Per user, stored in `user.settings.functions.valves[function_id]` |
| Access | `self.valves.field_name` | `__user__["valves"].field_name` |
| Use cases | API keys, service URLs, global configuration | User preferences, personal toggles |

## Accessing Valves — Watch Out for the Trap

```python
# CORRECT: attribute access
self.valves.api_key
__user__["valves"].preference

# INCORRECT: dictionary access returns default value, not actual value!
__user__["valves"]["preference"]  # ← DEFAULT VALUE, NOT ACTUAL VALUE
```

## Field Types

### Basic Types

```python
from pydantic import BaseModel, Field
from typing import Literal

class Valves(BaseModel):
    # Integer
    test_valve: int = Field(default=4, description="...")

    # Boolean (rendered as switch in UI)
    test_user_valve: bool = Field(default=False, description="...")

    # String with limited choices
    choice_option: Literal["choiceA", "choiceB"] = Field(default="choiceA", description="...")
```

### Password Field (hidden in UI)

```python
service_password: str = Field(
    default="",
    description="Your service password",
    json_schema_extra={"input": {"type": "password"}}
)
```

### Static Dropdown Select

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

### Dynamic Dropdown Select

The method name (string) is called dynamically to populate options.

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
    # __user__ is automatically injected (like a reserved arg)
    # when the user opens the settings, otherwise None
    return [
        {"value": "gpt-4", "label": "GPT-4"},
        {"value": "gpt-3.5-turbo", "label": "GPT-3.5 Turbo"}
    ]
```

### Required Field

```python
api_key: str = Field(default="", description="API key", required=True)
```

> **`required=True` validation:** On the UI side, an empty required field displays a visual warning but does not block execution. On the backend, Pydantic validation only applies if the default value is absent — with `default=""`, an empty field passes validation. For real blocking, do not provide a default value.

## Priority Field

```python
priority: int = Field(default=0, description="Lower values execute first")
```

Lower values execute first. This field controls:

- Execution order of Filters (inlet/outlet)
- Display order of Action buttons (ascending priority, then alphabetical by function ID if equal)

## Complete Example

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

## Persistence Mechanism

### Valves (admin)

Stored in the `valves` column (JSONField) of the corresponding `function` or `tool` table. Read via `get_function_valves_by_id()` / equivalent tool, write via `update_function_valves_by_id()`. Accessible to all plugin executions.

### UserValves

Stored in `user.settings.functions.valves[function_id]` (JSON nested in user settings). Read via `get_user_valves_by_id_and_user_id()`. Each user has their own values, independent of each other.
