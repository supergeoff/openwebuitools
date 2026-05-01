# Design Spec — Question Wizard (v2.0)

**Date:** 2026-05-01
**Author:** supergeoff
**Status:** Approved — implementation ready

---

## 1. Objective

Refactor the existing `questionnaire_wizard.py` tool into `question_wizard.py` with the following goals:

1. **Rename** all user-facing references from "Questionnaire Wizard" to "Question Wizard".
2. **Monochrome UI** — replace all blue/green/colored CSS with a strict black/white/grey palette.
3. **Fix double-launch (Type A)** — strengthen the docstring to explicitly warn the LLM to call the function **exactly once**.
4. **Fix empty message bug** — correct the `postMessage` payload format so answers are properly injected into the chat.

---

## 2. Changes Overview

| # | Change | File | Detail |
|---|--------|------|--------|
| 1 | Rename file | `tools/questionnaire_wizard.py` → `tools/question_wizard.py` | Disk-level rename |
| 2 | Rename title | `tools/question_wizard.py` frontmatter | `title: Question Wizard` |
| 3 | Rename method | `tools/question_wizard.py` | `run_questionnaire` → `run_question_wizard` |
| 4 | Monochrome CSS | `_HTML_TEMPLATE` inline CSS | Replace `#2563eb`, `#059669`, `#bfdbfe`, `#eff6ff`, `#ecfdf5` with black/white/grey equivalents |
| 5 | Strengthen docstring | `run_question_wizard` docstring | Add: *"⚠️ Call this function EXACTLY ONCE per turn. Do NOT call it multiple times."* |
| 6 | Fix postMessage | JS `submit()` function | Change payload from `{ type: "input:prompt:submit", data: { text: md } }` to `{ type: "input:prompt:submit", text: md }` |

---

## 3. CSS Color Mapping

| Original Color | Usage | New Color |
|----------------|-------|-----------|
| `#2563eb` | Buttons, progress bar, accent-color, focus borders | `#000000` |
| `#1d4ed8` | Button hover | `#333333` |
| `#059669` | Confirmation text | `#000000` |
| `#ecfdf5` | Confirmation background | `#f5f5f5` |
| `#bfdbfe` | Option hover border | `#999999` |
| `#eff6ff` | Option hover background | `#f0f0f0` |
| `#1f2937` | Body text | `#000000` |
| `#111827` | Title text | `#000000` |
| `#374151` | Label text | `#333333` |
| `#6b7280` | Description, counter text | `#666666` |
| `#e5e7eb` | Borders, progress track bg | `#e0e0e0` |
| `#d1d5db` | Input borders, skip border | `#cccccc` |
| `#f3f4f6` | Prev button bg | `#f0f0f0` |
| `#f9fafb` | Body bg, option row bg | `#fafafa` |

All transitions remain but colors are strictly in the greyscale spectrum.

---

## 4. postMessage Fix

Current (broken):
```js
parent.postMessage({ type: "input:prompt:submit", data: { text: md } }, "*");
```

Fixed:
```js
parent.postMessage({ type: "input:prompt:submit", text: md }, "*");
```

Rationale: OpenWebUI's Rich UI embeds expect the `text` key at the top level of the payload, not nested inside `data`.

---

## 5. File Structure

```
tools/
  question_wizard.py      ← renamed from questionnaire_wizard.py
```

The tool remains a **single self-contained file** with inline HTML/CSS/JS — preferred by OpenWebUI for easy copy-paste deployment.

---

## 6. Validation Checklist

- [ ] File renamed on disk
- [ ] Old `questionnaire_wizard.py` removed
- [ ] Frontmatter title reads `Question Wizard`
- [ ] Method name is `run_question_wizard`
- [ ] No blue/green color remains in CSS
- [ ] `postMessage` sends `text` at top level
- [ ] Docstring contains "exactly once" warning
- [ ] Tool loads correctly in OpenWebUI
- [ ] Wizard renders in monochrome
- [ ] Submitting answers injects a non-empty markdown message
