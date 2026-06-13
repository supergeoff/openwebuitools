---
name: question
description: "Use when an agent needs answers, preferences, requirements, feedback, survey data, or clarifications from the user in Open WebUI; route questions through Question Wizard instead of plain chat."
tags: ["openwebui", "tools", "interaction", "questionnaire", "ux"]
---

# Ask Questions via Question Wizard

When you need information from the user, use `run_question_wizard`; do not ask questions as plain text in chat. This skill targets Question Wizard version 0.6.5.

## Universal Router

This skill is the routing point for user questions. Any other skill or context that needs user input must use `run_question_wizard`, including brainstorming, requirement clarification, feedback collection, assumption checks, and survey flows.

Only skip the wizard when the user explicitly opts out, for example: "just guess", "decide yourself", or "do not ask me".

<HARD-GATE>
Do NOT write questions as plain text in your response.
Do NOT call `run_question_wizard` more than once per user request.
Build all questions into one JSON value, serialize it with `json.dumps(...)`, and pass that JSON string to `run_question_wizard`.
</HARD-GATE>

## Invocation Rules

| Rule | Requirement |
|---|---|
| One call | Put every question in one payload and call `run_question_wizard` once. |
| JSON string | The function argument is a string produced by `json.dumps(...)`, not a Python dict or list. |
| Canonical payload | Prefer the canonical shape: one root object with `questions`. |
| Proposals | `single` and `multiple` questions require 2-4 proposal strings. |
| Text questions | Use `type: "text"` for open-ended answers; do not invent fake proposals. |

The tool has two duplicate protections. Concurrent non-identical calls hit the class-level lock and return an error. Duplicate identical calls by the same user within 8 seconds return a blank 1px response, so never retry the same payload as a second wizard.

## Canonical JSON Shape

Use this canonical shape even though the tool is tolerant of legacy shorthand inputs:

```python
import json

questions_json = json.dumps({
    "title": "Project Discovery",       # optional
    "description": "Short context",      # optional
    "submit_label": "Submit",            # optional, default `"Submit"`
    "questions": [                       # required, 1-13 items
        {
            "id": "priority",            # optional stable machine key
            "question": "What matters most?",
            "type": "single",
            "proposals": ["Speed", "Quality", "Cost"],
            "required": True
        }
    ]
})
```

## Question Object

| Key | Applies to | Notes |
|---|---|---|
| `question` | all | Required user-facing question text. |
| `type` | all | Use `single`, `multiple`, or `text`; include it for clarity. |
| `proposals` | `single`, `multiple` | Required, 2-4 strings. |
| `id` | all | Optional stable machine-readable identifier; defaults to `q1`, `q2`, etc. |
| `required` | all | Optional boolean, default `false`. |
| `allow_text` | `single`, `multiple` | Optional boolean, default `true`; adds an "Other" text option. |
| `placeholder` | `text` | Optional text-area placeholder. |
| `other_label` | `single`, `multiple` | Optional label for the free-text option. |
| `other_placeholder` | `single`, `multiple` | Optional placeholder for the free-text option. |
| `min_selections` | `multiple` | Optional integer; default is `1` when required, otherwise `0`. |
| `max_selections` | `multiple` | Optional integer; cannot exceed available choices plus the text option when enabled. |
| `min_length` | `text` | Optional integer; default is `1` when required, otherwise `0`. |
| `max_length` | `text` | Optional integer; must be greater than or equal to `min_length`. |

For `single`, `required: true` means one answer is required and `max_selections` is always 1. For `text`, `allow_text` is ignored because the answer itself is free text.

## Accepted Aliases

Prefer canonical keys, but the tool accepts model-friendly aliases:

| Canonical | Accepted aliases |
|---|---|
| `proposals` | `options`, `choices`, `answers` |
| `id` | `key`, `name` |
| `type: "single"` | `single_choice`, `radio` |
| `type: "multiple"` | `multi_choice`, `checkbox` |
| `type: "text"` | `open`, `textarea` |

The aliases `key` and `name` are accepted for `id`. If `type` is missing but proposals are present, the tool defaults to `single` and may emit a warning.

## Examples

### Requirements Clarification

```python
import json

await run_question_wizard(json.dumps({
    "title": "Build Scope",
    "description": "Choose the constraints before implementation.",
    "questions": [
        {
            "id": "scope",
            "question": "Which scope should I implement first?",
            "type": "single",
            "proposals": ["Core flow", "Admin flow", "Reporting"],
            "required": True
        },
        {
            "id": "constraints",
            "question": "Which constraints matter?",
            "type": "multiple",
            "proposals": ["Speed", "Maintainability", "Low cost", "Security"],
            "required": True,
            "min_selections": 1,
            "max_selections": 2,
            "allow_text": True,
            "other_label": "Other:",
            "other_placeholder": "Type another constraint"
        },
        {
            "id": "notes",
            "question": "Anything else I should know?",
            "type": "text",
            "placeholder": "Add context, edge cases, or exclusions...",
            "max_length": 500
        }
    ]
}))
```

### Feedback Collection

```python
import json

await run_question_wizard(json.dumps({
    "title": "Design Feedback",
    "questions": [
        {
            "id": "fit",
            "question": "Does this match your intent?",
            "type": "single",
            "proposals": ["Yes", "Partially", "No"],
            "required": True,
            "allow_text": False
        },
        {
            "id": "changes",
            "question": "What should change?",
            "type": "text",
            "required": True,
            "min_length": 5
        }
    ]
}))
```

## Common Mistakes

| Mistake | Fix |
|---|---|
| Asking follow-up questions in plain text | Use one `run_question_wizard` payload. |
| Calling the wizard twice | Merge every question into one payload before calling. |
| Passing a dict directly | Pass `json.dumps(payload)`. |
| Using one proposal | Add a second balanced proposal or use `type: "text"`. |
| Using more than four proposals | Reduce to the four most useful choices or use text. |
| Relying on shorthand payloads | Use the canonical shape with a root object and `questions`. |
| Retrying the same payload | Avoid duplicate identical calls; the second returns a blank 1px response. |
| Adding biased choices | Use neutral proposals or a text question. |

## One-Line Cue

Before calling the tool, say: "I need user input -> one canonical JSON object -> `json.dumps(...)` -> one `run_question_wizard` call -> `single`/`multiple` use 2-4 balanced proposals."
