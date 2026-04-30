# Design Spec — Visual Questionnaire Wizard for Open WebUI

**Date:** 2026-04-29
**Author:** supergeoff
**Status:** Draft — awaiting user review

---

## 1. Objective

Create an **Open WebUI Tool** callable by the LLM that displays a **visual interactive questionnaire** (1 to 13 questions) in a sandboxed iframe via Rich UI Embedding. The user navigates between questions, selects predefined proposals and/or types free text, then sends their answers back to the LLM as a new injected message in the conversation.

**Visual reference:** Claude Co-workers (interactive questionnaire embedded in chat).

### Language Constraint

All code, frontmatter, docstrings, comments, and variable names **must be in English**. The user-facing UI text (labels, buttons, placeholder) may remain in French as requested by the user, but all backend code and documentation are strictly English.

---

## 2. Architecture

```
+----------------------------------------------------------+
|                       OPEN WEBUI                         |
+----------------------------------------------------------+
|                                                          |
|  1. LLM generates a questions JSON                       |
|     -> Calls tool: run_questionnaire(questions_json)     |
|                                                          |
|  2. Tool parses JSON, generates full HTML                |
|     -> Returns HTMLResponse(content=html, headers=...)   |
|     -> Open WebUI injects iframe inline in chat          |
|                                                          |
|  3. User interacts in sandboxed iframe (vanilla JS SPA)  |
|     -> Navigation prev/next/skip, selections, free text  |
|     -> State managed entirely in JS memory               |
|                                                          |
|  4. "Submit" button -> postMessage to parent             |
|     -> parent.postMessage({type:'input:prompt:submit'})  |
|     -> Open WebUI creates a new user message             |
|     -> LLM receives formatted markdown answers           |
|                                                          |
+----------------------------------------------------------+
```

**Approach:** Monolithic Batch (all questions passed in ONE call).

---

## 3. Tool API

### Exposed Method

```python
async def run_questionnaire(
    self,
    questions_json: str,
    __user__: dict = None,
) -> tuple[HTMLResponse, dict]:
    """
    Launches a visual interactive questionnaire with question navigation.
    The user selects predefined proposals and/or types free text,
    then sends their answers back to the LLM via message injection.

    :param questions_json: JSON string describing the questionnaire.
        Expected format:
        {
            "title": "string (optional)",
            "description": "string (optional)",
            "submit_label": "string (optional, default: 'Envoyer')",
            "questions": [
                {
                    "question": "string (required)",
                    "type": "string — 'single' or 'multiple'",
                    "proposals": ["string", "string", ...],  // 2 to 4 items
                    "allow_text": "bool (optional, default: true)"
                }
            ]  // 1 to 13 questions
        }
    """
```

### Return Value

The tool returns a **tuple** `(HTMLResponse, context_dict)`:

- `HTMLResponse(content=html, headers={"Content-Disposition": "inline"})` -> Visual iframe rendering
- `context_dict` -> Context visible by the LLM (e.g. `{"status": "questionnaire_active", "questions_count": 5}`)

### Input Validation

| Rule | Error Behavior |
|------|----------------|
| Malformed JSON | Returns plain text error message (no HTMLResponse) |
| 0 or >13 questions | Returns plain text error message |
| Question without `question` field | Returns plain text error message |
| Question without `type` or invalid type | Defaults to `"single"` |
| Question without `proposals` or <2 proposals | Returns plain text error message |
| `allow_text` missing | Defaults to `true` |

---

## 4. Answer Format (Output)

The "Submit" button (or "Skip the rest") injects into the chat a formatted user message in markdown:

```markdown
## 📝 Questionnaire: {title}

**{description}** (if present)

1. {question}
   -> {selected_answers} *(or "(non répondu)")*

2. {question}
   -> {selected_answers}

...

---
*Answers submitted via Questionnaire Wizard*
```

**Formatting Rules:**
- If multiple answers selected -> separated by `, `
- If free text checked AND proposals checked -> free text is appended to the list
- If no answer for a question -> `"(non répondu)"`
- If intermediate skip -> unvisited questions are `"(non répondu)"`

---

## 5. User Interface (Wizard)

### Per-Question Layout

```
+------------------------------------------------------+
|  📋 {title}                              [{i}/{n}]   |
|  {description}                                       |
+------------------------------------------------------+
|                                                      |
|  Question {i}/{n}: {question}                        |
|                                                      |
|  ○ {proposal_1}                                      |
|  ○ {proposal_2}                                      |
|  ○ {proposal_3}                                      |
|                                                      |
|  ○ [_________________________]  (free text)          |
|                                                      |
|         [← Précédent]  [Suivant →]                   |
|                    [Skip le reste]                   |
|                                                      |
+------------------------------------------------------+
```

### Last Question

The "Suivant →" button is replaced by `[{submit_label}]` (default: "Envoyer").

### UI Elements

| Element | Behavior |
|---------|----------|
| **Counter** | `{i}/{n}` top right |
| **Single type** | Radio buttons for proposals. Free text is the **last option of the radio group** (same circle, mutually exclusive with proposals). |
| **Multiple type** | Checkboxes for proposals AND for free text (independent multiple selections). |
| **Proposals** | Each line = radio/checkbox + clickable label |
| **Free text** | Separate line below proposals. For **single**: radio button of the same group (selecting free text deselects proposals, and vice versa). For **multiple**: independent checkbox. Text input displayed next to it. When active (checked/selected), the input value is included in answers. Empty input but active = empty string included. |
| **Previous** | Disabled if question 1/1, hidden if question 1/n (n>1) |
| **Next** | Always active (does not check for mandatory answer) |
| **Skip** | Immediate send of current answers |
| **Submit** | On last question, replaces "Next" |
| **allow_text: false** | No free text line displayed for this question |

---

## 6. JavaScript Logic (inline in HTML)

### State

```javascript
const state = {
    currentIndex: 0,           // Current question index
    answers: [],               // Array of {question, type, proposals, selected:[], text_active:false, text_value:""}
    config: {}                 // {title, description, submit_label}
};
```

### Navigation

```
prevQuestion()  -> currentIndex-- (min 0)
nextQuestion()  -> currentIndex++ (max n-1, on last -> submit)
skip()          -> submit with current state
```

### Answer Collection

```javascript
function buildResponse() {
    return state.answers.map((a, idx) => ({
        question: a.question,
        selected: [
            ...a.selected,
            ...(a.text_active ? [a.text_value] : [])
        ].filter(v => v !== null && v !== undefined && v !== "")
    }));
}
```

### Final Submission

```javascript
function submit() {
    const responses = buildResponse();
    const lines = responses.map((r, i) => {
        const answers = r.selected.length ? r.selected.join(', ') : '(non répondu)';
        return `${i+1}. ${r.question}\n   -> ${answers}`;
    });
    const text = `## 📝 Questionnaire: ${state.config.title}\n\n${lines.join('\n\n')}\n\n---\n*Answers submitted via Questionnaire Wizard*`;
    parent.postMessage({type: 'input:prompt:submit', text}, '*');
}
```

### Iframe Auto-Resize

```javascript
function reportHeight() {
    const h = document.documentElement.scrollHeight;
    parent.postMessage({type: 'iframe:height', height: h}, '*');
}
window.addEventListener('load', reportHeight);
new ResizeObserver(reportHeight).observe(document.body);
```

---

## 7. Constraints & Limitations

| Constraint | Decision |
|-----------|----------|
| **allowSameOrigin** | OFF by default. The wizard runs entirely within the iframe without needing `localStorage` or parent DOM access |
| **Persistence** | Answers do not survive a browser F5 (no localStorage). The wizard is recreated from the HTML stored in DB |
| **Mandatory answers** | NONE. The user can advance without answering, and submit at any time via "Skip" |
| **Post-submit editing** | Impossible. Once "Submit" is clicked, the wizard is "frozen" (buttons disabled, confirmation message) |
| **Max size** | Inline HTML is limited by Open WebUI storage capabilities. A 13-question questionnaire with 4 proposals each is well within limits |
| **Timeout** | None. The wizard waits indefinitely for user interaction |

---

## 8. Error Handling

| Scenario | Behavior |
|----------|----------|
| Malformed JSON | Tool returns `"Error: Invalid JSON. Please check the syntax of the questions_json parameter."` |
| 0 or >13 questions | Tool returns `"Error: The questionnaire must contain between 1 and 13 questions."` |
| Proposals < 2 | Tool returns `"Error: Each question must have at least 2 proposals."` |
| Invalid type | Defaults to `"single"` (silent console warning) |

---

## 9. Security

HTML content is generated server-side by the Python tool. No user content is interpreted as code:

- Questions and proposals are **HTML-escaped** (`<` -> `&lt;`, etc.)
- JS is static and inline, no `eval()` or `innerHTML` with dynamic content
- User inputs (free text) are never re-injected into the wizard DOM after submission

---

## 10. Deliverables

| File | Description |
|------|-------------|
| `tools/questionnaire_wizard.py` | Complete Open WebUI Tool |
| `tools/questionnaire_wizard.html` | Wizard HTML template (not used directly, embedded in the .py) |

---

## 11. LLM Call Example

```python
# The LLM builds this JSON and calls it via function calling
{
    "questions_json": "{\"title\":\"Project Configuration\",\"description\":\"Help me configure your tool.\",\"questions\":[{\"question\":\"Main language?\",\"type\":\"single\",\"proposals\":[\"Python\",\"TypeScript\",\"Rust\"],\"allow_text\":true},{\"question\":\"Preferred frameworks?\",\"type\":\"multiple\",\"proposals\":[\"FastAPI\",\"Django\",\"Express\",\"NestJS\"],\"allow_text\":true}]}"
}
```

---

## 12. Dependencies

No external dependencies required. The tool uses only:
- `json` (stdlib)
- `html` (stdlib for escaping)
- `fastapi.responses.HTMLResponse`

---

## 13. Validation Checklist

- [ ] Tool appears correctly in Open WebUI tools list
- [ ] LLM can call it via function calling
- [ ] Wizard displays inline in chat
- [ ] Prev/next navigation works
- [ ] Skip works and sends answers
- [ ] "Submit" button on last question injects a message into chat
- [ ] Injected message is properly formatted in markdown
- [ ] LLM receives answers and can exploit them
- [ ] Iframe resizes correctly
- [ ] Special characters in questions/proposals are properly escaped
