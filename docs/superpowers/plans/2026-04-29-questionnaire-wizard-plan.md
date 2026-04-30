# Implementation Plan — Questionnaire Wizard Tool

**Date:** 2026-04-29
**Spec:** `docs/superpowers/specs/2026-04-29-questionnaire-wizard-design.md`

## Deliverable

Single file: `tools/questionnaire_wizard.py`

## Steps

### Step 1 — Scaffold the Tool file
- Frontmatter (title, author, version, description)
- `class Tools` with `Valves` (empty/default)
- `__init__` with `self.citation = False`

### Step 2 — Input validation
- Parse `questions_json` string to dict
- Validate: 1-13 questions, each has `question` and `proposals` (>=2)
- Return plain error string (not HTMLResponse) on validation failure

### Step 3 — HTML generation function
- `_generate_html(config: dict) -> str`
- Escape all user-provided strings with `html.escape()`
- Embed the complete SPA (CSS + JS + HTML) as a single string
- CSS: clean card layout, radio/checkbox styling, responsive
- JS: state management, navigation, answer collection, postMessage submit
- Include iframe auto-resize via postMessage

### Step 4 — Tool method
- `async def run_questionnaire(self, questions_json: str, __user__: dict = None)`
- Docstring in English per user requirement
- Full type hints (Open WebUI only supports str/int/float/bool)
- Return tuple: `(HTMLResponse(headers={"Content-Disposition": "inline"}), context_dict)`

### Step 5 — Final polish
- Test-read the file for syntax errors
- Ensure all strings/comments/docstrings are English
- Verify no external dependencies beyond stdlib + HTMLResponse

## Estimated Effort

Single implementation session. File length: ~400-500 lines.
