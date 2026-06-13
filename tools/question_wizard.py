"""
title: Question Wizard
author: supergeoff
version: 0.6.5
description: |
    Interactive visual questionnaire for Open WebUI.

    IMPORTANT:
      Call `run_question_wizard` EXACTLY ONCE per user request.
      Parameter: a single JSON string produced by `json.dumps(...)`.

    ROOT OBJECT — required keys:
      • "questions": array of 1-13 question objects (REQUIRED)
      • "title": string (optional)
      • "description": string (optional)
      • "submit_label": string, default "Submit" (optional)

    QUESTION OBJECT — required keys:
      • "question": string (REQUIRED)
      • "type": "single" | "multiple" | "text" (REQUIRED for clarity)
      • "proposals": ["A","B",...] (REQUIRED for single/multiple — 2 to 4 items)

    QUESTION OBJECT — optional keys:
      • "id": stable machine-readable identifier, e.g. "priority"
      • "required": true | false, default false
      • "allow_text": true | false, default true for single/multiple
      • "placeholder": string, for text questions
      • "other_label": string, default "Other:"
      • "other_placeholder": string, default "Type here..."
      • "min_selections": integer, for multiple questions
      • "max_selections": integer, for multiple questions
      • "min_length": integer, for text questions
      • "max_length": integer, for text questions

    TOLERANCE:
      • "options", "choices", "answers" are accepted as aliases for "proposals".
      • Missing "type" with "proposals" present defaults to "single".
      • "key" and "name" are accepted as aliases for "id".

    SUBMITTED OUTPUT:
      The wizard submits a clean human-readable Markdown summary only:
      title, optional description, questions, and answers.

    TRANSLATION:
      User-facing strings are centralised in `_UI_TEXT`.
      Translate that block only, keeping keys and `{placeholder}` names intact.

    Depends: fastapi.responses.HTMLResponse
"""

import asyncio
import hashlib
import json
import re
import secrets
import time
from typing import Any

from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

_VERSION = "0.6.5"

_MAX_QUESTIONS = 13
_MAX_PROPOSALS = 4
_MIN_PROPOSALS = 2

_DEDUPE_SECONDS = 8

_TYPE_ALIASES = {
    "single": "single",
    "single_choice": "single",
    "radio": "single",
    "multiple": "multiple",
    "multi_choice": "multiple",
    "checkbox": "multiple",
    "text": "text",
    "open": "text",
    "textarea": "text",
}

_PROPOSAL_ALIASES = ("proposals", "options", "choices", "answers")
_ID_ALIASES = ("id", "key", "name")

_ID_SAFE_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


# ---------------------------------------------------------------------------
# TRANSLATION BLOCK — USER-FACING STRINGS
# ---------------------------------------------------------------------------
# Translate values only.
# Keep keys unchanged.
# Keep placeholder names unchanged, e.g. {index}, {min}, {max}, {count}.
# ---------------------------------------------------------------------------

_UI_TEXT = {
    # General UI
    "default_title": "Question Wizard",
    "submit_label": "Submit",
    "previous_label": "← Previous",
    "next_label": "Next →",
    "finish_now_label": "Finish now",
    "already_submitted": "✅ Answers already submitted.",
    "answers_submitted_confirmation": "✅ Answers submitted.",
    "warning_prefix": "⚠️ ",
    "warning_joiner": " | ",

    # Question metadata
    "required_label": "Required",
    "optional_label": "Optional",
    "select_range": "Select {min}-{max}",
    "select_at_least": "Select at least {min}",
    "select_up_to": "Select up to {max}",
    "select_any": "Select any that apply",
    "characters_range": "{min}-{max} characters",
    "characters_min": "At least {min} characters",
    "characters_max": "Up to {max} characters",
    "meta_separator": " · ",

    # Inputs
    "text_placeholder": "Type your answer...",
    "other_label": "Other:",
    "other_placeholder": "Type here...",
    "unanswered": "(unanswered)",

    # Validation messages
    "validation_text_required": "Please enter an answer before continuing.",
    "validation_text_min_length": "Please enter at least {min} character(s).",
    "validation_text_max_length": "Please enter no more than {max} character(s).",
    "validation_choice_required": "Please select an answer before continuing.",
    "validation_multiple_min": "Please select at least {min} option(s).",
    "validation_multiple_max": "Please select no more than {max} option(s).",

    # Submitted Markdown
    "markdown_heading_prefix": "## 📝 Question Wizard: ",
    "answer_arrow": "→",
    "answers_submitted_footer": "*Answers submitted via Question Wizard*",

    # Python/tool errors and warnings
    "error_question_not_object": "Error: Question {index} is not a valid object.",
    "error_missing_question": "Error: Missing or invalid 'question' field in question {index}.",
    "warning_invalid_type": "Warning: question {index} had no valid type; defaulted to 'single'.",
    "error_bad_proposal_count": (
        "Error: single/multiple questions need {min}-{max} proposals "
        "(question {index}, got {count})."
    ),
    "error_text_too_many_proposals": "Error: At most {max} proposals allowed (question {index}).",
    "error_min_selections_negative": "Error: min_selections cannot be negative in question {index}.",
    "error_min_selections_too_high": "Error: min_selections cannot exceed available answers in question {index}.",
    "error_max_less_than_min": "Error: max_selections cannot be less than min_selections in question {index}.",
    "error_max_selections_too_high": "Error: max_selections cannot exceed available answers in question {index}.",
    "error_min_length_negative": "Error: min_length cannot be negative in question {index}.",
    "error_max_length_less_than_min": "Error: max_length cannot be less than min_length in question {index}.",
    "error_invalid_json": "Error: Invalid JSON -- {error}",
    "error_root_not_object": "Error: The root element must be a JSON object with a 'questions' array.",
    "error_questions_array": "Error: 'questions' must be an array with 1-{max} items.",
    "warning_duplicate_id": "Warning: duplicate question id '{old}' renamed to '{new}'.",
    "error_already_running": (
        "Error: Question Wizard is already running. "
        "You called `run_question_wizard` more than once in the same turn. "
        "Build all questions into a single JSON object and call the tool exactly once."
    ),
}


# ---------------------------------------------------------------------------
# STRING HELPERS
# ---------------------------------------------------------------------------


def _txt(key: str, **kwargs) -> str:
    """Return a translated UI string formatted with kwargs."""
    value = _UI_TEXT.get(key, key)

    if kwargs:
        try:
            return value.format(**kwargs)
        except Exception:
            return value

    return value


# ---------------------------------------------------------------------------
# NORMALISATION HELPERS
# ---------------------------------------------------------------------------


def _extract_proposals(q: dict) -> list[Any]:
    """Return proposals list from the first matching alias key."""
    for key in _PROPOSAL_ALIASES:
        if key in q:
            val = q[key]
            if isinstance(val, list):
                return val
    return []


def _extract_id(q: dict, idx: int) -> str:
    """Return a normalised stable question ID."""
    raw_id = None

    for key in _ID_ALIASES:
        if key in q:
            raw_id = q.get(key)
            break

    if not isinstance(raw_id, str) or not raw_id.strip():
        return f"q{idx + 1}"

    cleaned = _ID_SAFE_RE.sub("_", raw_id.strip())[:80].strip("_")
    return cleaned or f"q{idx + 1}"


def _clean_string(value: Any, default: str = "") -> str:
    """Convert a value to a clean string."""
    if value is None:
        return default

    cleaned = str(value).strip()
    return cleaned if cleaned else default


def _clean_proposals(proposals: Any) -> list[str]:
    """Normalise proposal values to non-empty strings."""
    if not isinstance(proposals, list):
        return []

    cleaned = []
    for prop in proposals:
        val = _clean_string(prop)
        if val:
            cleaned.append(val)

    return cleaned


def _as_bool(value: Any, default: bool = False) -> bool:
    """Coerce common boolean-like values to bool."""
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "y", "1", "on"):
            return True
        if lowered in ("false", "no", "n", "0", "off"):
            return False

    return default


def _as_int(value: Any, default: int | None = None) -> int | None:
    """Coerce value to int, returning default if blank or invalid."""
    if value is None or value == "":
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _canonical_json_for_hash(value: Any) -> str:
    """Return deterministic JSON for hashing."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _blank_duplicate_response() -> HTMLResponse:
    """Return a tiny invisible response for rare duplicate tool execution."""
    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
html, body {
  margin: 0;
  padding: 0;
  height: 1px;
  min-height: 1px;
  overflow: hidden;
  background: transparent;
}
</style>
</head>
<body>
<script>
try {
  parent.postMessage({ type: "iframe:height", height: 1 }, "*");
} catch (e) {}
</script>
</body>
</html>"""
    return HTMLResponse(
        content=html,
        headers={"Content-Disposition": "inline"},
    )


# ---------------------------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------------------------


def _validate_question(q: dict, idx: int) -> dict | str | tuple[dict, str]:
    """
    Normalise and validate a single question.

    Returns:
      • dict — normalised question
      • str — fatal error message
      • tuple (dict, str) — normalised question plus warning
    """
    index = idx + 1

    if not isinstance(q, dict):
        return _txt("error_question_not_object", index=index)

    question_text = _clean_string(q.get("question"))
    if not question_text:
        return _txt("error_missing_question", index=index)

    q_id = _extract_id(q, idx)
    raw_type = q.get("type", "")
    proposals = _clean_proposals(_extract_proposals(q))

    inferred_type = None
    warning = None

    if not raw_type:
        if len(proposals) >= _MIN_PROPOSALS:
            inferred_type = "single"
    else:
        inferred_type = _TYPE_ALIASES.get(str(raw_type).lower().strip())
        if inferred_type is None and len(proposals) >= _MIN_PROPOSALS:
            inferred_type = "single"

    if inferred_type is None:
        inferred_type = "single"
        warning = _txt("warning_invalid_type", index=index)

    q_type = inferred_type

    if q_type in ("single", "multiple"):
        if not (_MIN_PROPOSALS <= len(proposals) <= _MAX_PROPOSALS):
            return _txt(
                "error_bad_proposal_count",
                min=_MIN_PROPOSALS,
                max=_MAX_PROPOSALS,
                index=index,
                count=len(proposals),
            )

    elif q_type == "text":
        if len(proposals) > _MAX_PROPOSALS:
            return _txt(
                "error_text_too_many_proposals",
                max=_MAX_PROPOSALS,
                index=index,
            )

    required = _as_bool(q.get("required"), False)

    allow_text = (
        False
        if q_type == "text"
        else _as_bool(q.get("allow_text"), True)
    )

    min_selections = 0
    max_selections = None
    min_length = 0
    max_length = None

    if q_type == "single":
        min_selections = 1 if required else 0
        max_selections = 1

    elif q_type == "multiple":
        max_possible = len(proposals) + (1 if allow_text else 0)

        min_selections = _as_int(
            q.get("min_selections"),
            1 if required else 0,
        )
        max_selections = _as_int(q.get("max_selections"), None)

        if min_selections is None:
            min_selections = 0

        if min_selections < 0:
            return _txt("error_min_selections_negative", index=index)

        if min_selections > max_possible:
            return _txt("error_min_selections_too_high", index=index)

        if max_selections is not None:
            if max_selections < min_selections:
                return _txt("error_max_less_than_min", index=index)

            if max_selections > max_possible:
                return _txt("error_max_selections_too_high", index=index)

    elif q_type == "text":
        min_length = _as_int(
            q.get("min_length"),
            1 if required else 0,
        )
        max_length = _as_int(q.get("max_length"), None)

        if min_length is None:
            min_length = 0

        if min_length < 0:
            return _txt("error_min_length_negative", index=index)

        if max_length is not None and max_length < min_length:
            return _txt("error_max_length_less_than_min", index=index)

    norm = {
        "id": q_id,
        "question": question_text,
        "type": q_type,
        "proposals": proposals,
        "required": required,
        "allow_text": allow_text,
        "placeholder": (
            _clean_string(q.get("placeholder"), _txt("text_placeholder"))
            if q_type == "text"
            else ""
        ),
        "other_label": (
            _clean_string(q.get("other_label"), _txt("other_label"))
            if q_type != "text"
            else ""
        ),
        "other_placeholder": (
            _clean_string(q.get("other_placeholder"), _txt("other_placeholder"))
            if q_type != "text"
            else ""
        ),
        "min_selections": min_selections,
        "max_selections": max_selections,
        "min_length": min_length,
        "max_length": max_length,
    }

    if warning:
        return (norm, warning)

    return norm


# ---------------------------------------------------------------------------
# HTML TEMPLATE
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Question Wizard</title>
<style>
  /* Light-mode defaults */
  :root {
    --qw-text: #1e293b;
    --qw-text-dim: #475569;
    --qw-text-muted: #64748b;
    --qw-text-faint: #94a3b8;

    --qw-border: #e2e8f0;
    --qw-border-light: #cbd5e1;

    --qw-hover: rgba(0, 0, 0, 0.03);
    --qw-active: rgba(0, 0, 0, 0.10);

    --qw-field-bg: #ffffff;
    --qw-field-text: #1e293b;

    --qw-button-bg: rgba(0, 0, 0, 0.03);
    --qw-button-text: #1e293b;

    --qw-primary-bg: #000000;
    --qw-primary-text: #ffffff;

    --qw-danger-bg: rgba(239, 68, 68, 0.10);
    --qw-danger-border: rgba(239, 68, 68, 0.28);
    --qw-danger-text: #dc2626;

    --qw-warning-bg: rgba(245, 158, 11, 0.10);
    --qw-warning-border: rgba(245, 158, 11, 0.28);
    --qw-warning-text: #a16207;
  }

  /* Dark override — mirrors OWUI .dark class from parent */
  :root.dark {
    --qw-text: #e2e8f0;
    --qw-text-dim: #94a3b8;
    --qw-text-muted: #64748b;
    --qw-text-faint: #475569;

    --qw-border: rgba(255, 255, 255, 0.08);
    --qw-border-light: rgba(255, 255, 255, 0.12);

    --qw-hover: rgba(255, 255, 255, 0.04);
    --qw-active: rgba(255, 255, 255, 0.14);

    --qw-field-bg: rgba(255, 255, 255, 0.04);
    --qw-field-text: #e2e8f0;

    --qw-button-bg: rgba(255, 255, 255, 0.04);
    --qw-button-text: #e2e8f0;

    --qw-primary-bg: #ffffff;
    --qw-primary-text: #000000;

    --qw-danger-bg: rgba(239, 68, 68, 0.12);
    --qw-danger-border: rgba(239, 68, 68, 0.30);
    --qw-danger-text: #f87171;

    --qw-warning-bg: rgba(245, 158, 11, 0.12);
    --qw-warning-border: rgba(245, 158, 11, 0.28);
    --qw-warning-text: #fbbf24;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  html,
  body {
    background: transparent;
  }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: var(--qw-text);
    padding: 0;
    line-height: 1.45;
  }

  #app {
    width: 100%;
    max-width: none;
    margin: 0;
    background: transparent;
    border: none;
    border-radius: 0;
    overflow: visible;
    box-shadow: none;
  }

  #header {
    padding: 0 0 12px;
    border-bottom: 1px solid var(--qw-border);
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  #wizard-title {
    font-size: 1rem;
    font-weight: 650;
    color: var(--qw-text);
  }

  #wizard-desc {
    font-size: 0.85rem;
    color: var(--qw-text-muted);
    margin-top: 3px;
  }

  #wizard-counter {
    font-size: 0.78rem;
    color: var(--qw-text-muted);
    background: var(--qw-hover);
    border: 1px solid var(--qw-border);
    padding: 3px 8px;
    border-radius: 999px;
    white-space: nowrap;
  }

  #progress-track {
    height: 3px;
    background: var(--qw-hover);
    width: 100%;
    margin-top: 0;
  }

  #progress-bar {
    height: 100%;
    width: 0%;
    background: var(--qw-primary-bg);
    transition: width 0.3s ease;
  }

  #question-card {
    padding: 16px 0;
  }

  #question-title {
    font-size: 0.96rem;
    font-weight: 560;
    margin-bottom: 6px;
    color: var(--qw-text);
  }

  #question-meta {
    font-size: 0.78rem;
    color: var(--qw-text-muted);
    margin-bottom: 12px;
  }

  .option-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 10px;
    margin-bottom: 7px;
    border-radius: 8px;
    border: 1px solid var(--qw-border);
    background: transparent;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }

  .option-row:hover {
    border-color: var(--qw-border-light);
    background: var(--qw-hover);
  }

  input[type="radio"],
  input[type="checkbox"] {
    cursor: pointer;
    accent-color: var(--qw-primary-bg);
    width: 18px;
    height: 18px;
    flex-shrink: 0;
  }

  .option-row label {
    cursor: pointer;
    font-size: 0.9rem;
    color: var(--qw-text);
    flex: 1;
  }

  .free-text-row {
    align-items: center;
    gap: 8px;
  }

  .free-text-row label {
    flex: 0 0 auto;
    font-size: 0.9rem;
    color: var(--qw-text);
  }

  .free-text-input {
    flex: 1;
    min-width: 120px;
    background: var(--qw-field-bg);
    color: var(--qw-field-text);
    border: 1px solid var(--qw-border);
    border-radius: 7px;
    padding: 7px 8px;
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .free-text-input:focus {
    border-color: var(--qw-primary-bg);
    box-shadow: 0 0 0 3px var(--qw-active);
  }

  .free-text-input:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .free-textarea {
    width: 100%;
    min-height: 88px;
    background: var(--qw-field-bg);
    color: var(--qw-field-text);
    border: 1px solid var(--qw-border);
    border-radius: 8px;
    padding: 10px;
    font-size: 0.9rem;
    outline: none;
    resize: vertical;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .free-textarea:focus {
    border-color: var(--qw-primary-bg);
    box-shadow: 0 0 0 3px var(--qw-active);
  }

  #validation-message {
    display: none;
    margin-top: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--qw-danger-bg);
    border: 1px solid var(--qw-danger-border);
    color: var(--qw-danger-text);
    font-size: 0.85rem;
  }

  #nav-controls {
    padding: 12px 0 0;
    border-top: 1px solid var(--qw-border);
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }

  button {
    cursor: pointer;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 0.9rem;
    font-weight: 520;
    transition: background 0.15s, border-color 0.15s, transform 0.05s, opacity 0.15s;
  }

  button:active {
    transform: translateY(1px);
  }

  #btn-prev {
    margin-right: auto;
  }

  #btn-prev,
  #btn-finish {
    background: var(--qw-button-bg);
    color: var(--qw-button-text);
    border: 1px solid var(--qw-border);
  }

  #btn-prev:hover:not(:disabled),
  #btn-finish:hover:not(:disabled) {
    background: var(--qw-hover);
    border-color: var(--qw-border-light);
  }

  #btn-next {
    background: var(--qw-primary-bg);
    color: var(--qw-primary-text);
    border: 1px solid var(--qw-primary-bg);
  }

  #btn-next:hover:not(:disabled) {
    opacity: 0.86;
  }

  button:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .confirmation {
    margin-top: 12px;
    padding: 12px 14px;
    text-align: center;
    color: var(--qw-text);
    font-weight: 600;
    border: 1px solid var(--qw-border);
    border-radius: 8px;
    background: var(--qw-hover);
  }

  .warning-banner {
    padding: 8px 10px;
    background: var(--qw-warning-bg);
    color: var(--qw-warning-text);
    font-size: 0.85rem;
    border-bottom: 1px solid var(--qw-warning-border);
  }

  @media (max-width: 420px) {
    #header {
      flex-direction: column;
      align-items: stretch;
    }

    #wizard-counter {
      align-self: flex-start;
    }

    #nav-controls {
      align-items: stretch;
    }

    #btn-prev {
      margin-right: 0;
    }

    #btn-prev,
    #btn-next,
    #btn-finish {
      flex: 1 1 auto;
    }
  }
</style>
</head>
<body>
<div id="app">
  <div id="header">
    <div>
      <div id="wizard-title"></div>
      <div id="wizard-desc"></div>
    </div>
    <div id="wizard-counter"></div>
  </div>
  <div id="progress-track"><div id="progress-bar"></div></div>
  <div id="question-card">
    <h2 id="question-title"></h2>
    <div id="question-meta"></div>
    <div id="options-list"></div>
    <div id="validation-message" role="alert"></div>
  </div>
  <div id="nav-controls">
    <button id="btn-prev" type="button"></button>
    <button id="btn-next" type="button"></button>
    <button id="btn-finish" type="button"></button>
  </div>
</div>

<script id="wizard-config" type="application/json">__CONFIG_JSON__</script>

<script>
(function () {
  "use strict";

  var CONFIG = JSON.parse(document.getElementById("wizard-config").textContent);
  var TEXT = CONFIG.ui_text || {};

  function t(key, fallback) {
    if (Object.prototype.hasOwnProperty.call(TEXT, key)) {
      return TEXT[key];
    }
    return fallback;
  }

  function fmt(key, fallback, values) {
    var s = t(key, fallback);
    values = values || {};

    Object.keys(values).forEach(function (name) {
      s = s.split("{" + name + "}").join(String(values[name]));
    });

    return s;
  }

  function syncTheme() {
    try {
      var isDark = parent.document.documentElement.classList.contains("dark");
      document.documentElement.classList.toggle("dark", isDark);
    } catch (e) {
      document.documentElement.classList.remove("dark");
    }
  }

  syncTheme();

  try {
    new MutationObserver(syncTheme).observe(
      parent.document.documentElement,
      { attributes: true, attributeFilter: ["class"] }
    );
  } catch (e) {}

  var SESSION_KEY = "__SESSION_KEY__";
  var FORM_ID = CONFIG.form_id || SESSION_KEY;
  var RENDER_GROUP_ID = CONFIG.render_group_id || FORM_ID;
  var INSTANCE_ID = "qwi_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2);

  function reportHeight() {
    var h = document.documentElement.scrollHeight;
    parent.postMessage({ type: "iframe:height", height: h }, "*");
  }

  if (sessionStorage.getItem(SESSION_KEY)) {
    document.getElementById("app").innerHTML =
      '<div class="confirmation">' + t("already_submitted", "✅ Answers already submitted.") + '</div>';
    reportHeight();
    return;
  }

  var TOTAL = CONFIG.questions.length;
  var TITLE = CONFIG.title || t("default_title", "Question Wizard");
  var DESC = CONFIG.description || "";
  var SUBMIT = CONFIG.submit_label || t("submit_label", "Submit");
  var WARNINGS = CONFIG.warnings || [];

  var state = {
    idx: 0,
    frozen: false,
    answers: CONFIG.questions.map(function (q, idx) {
      var isText = q.type === "text";

      return {
        id: q.id || ("q" + (idx + 1)),
        question: q.question,
        type: isText ? "text" : (q.type === "multiple" ? "multiple" : "single"),
        proposals: q.proposals || [],
        required: !!q.required,
        allow_text: isText ? false : (q.allow_text !== false),
        placeholder: q.placeholder || t("text_placeholder", "Type your answer..."),
        other_label: q.other_label || t("other_label", "Other:"),
        other_placeholder: q.other_placeholder || t("other_placeholder", "Type here..."),
        min_selections: q.min_selections || 0,
        max_selections: q.max_selections || null,
        min_length: q.min_length || 0,
        max_length: q.max_length || null,
        selected: [],
        text_active: false,
        text_value: ""
      };
    })
  };

  var els = {
    title: document.getElementById("wizard-title"),
    desc: document.getElementById("wizard-desc"),
    counter: document.getElementById("wizard-counter"),
    qtitle: document.getElementById("question-title"),
    qmeta: document.getElementById("question-meta"),
    list: document.getElementById("options-list"),
    validation: document.getElementById("validation-message"),
    btnPrev: document.getElementById("btn-prev"),
    btnNext: document.getElementById("btn-next"),
    btnFinish: document.getElementById("btn-finish"),
    bar: document.getElementById("progress-bar")
  };

  var duplicateGuard = null;

  function installDuplicateRenderGuard() {
    var NS = "question_wizard_duplicate_guard_v1";
    var PEER_TTL_MS = 3000;
    var ELECTION_DELAY_MS = 350;
    var HEARTBEAT_MS = 750;

    var peers = {};
    var active = true;
    var interacted = false;
    var submitted = false;
    var electionTimer = null;

    var local = {
      ns: NS,
      render_group_id: RENDER_GROUP_ID,
      form_id: FORM_ID,
      instance_id: INSTANCE_ID,
      started_at: Date.now(),
      interacted: false,
      submitted: false,
      last_interaction_at: 0
    };

    function now() {
      return Date.now();
    }

    function updateLocal(extra) {
      Object.keys(extra || {}).forEach(function (key) {
        local[key] = extra[key];
      });
    }

    function cleanPeers() {
      var cutoff = now() - PEER_TTL_MS;

      Object.keys(peers).forEach(function (id) {
        if (!peers[id] || peers[id].last_seen < cutoff) {
          delete peers[id];
        }
      });
    }

    function sendToWindow(win, kind, extra) {
      if (!win || win === window) return;

      try {
        win.postMessage(
          Object.assign({}, local, extra || {}, {
            ns: NS,
            kind: kind,
            sent_at: now()
          }),
          "*"
        );
      } catch (e) {
        // Ignore unreachable windows.
      }
    }

    function broadcast(kind, extra) {
      updateLocal({
        interacted: interacted,
        submitted: submitted
      });

      try {
        sendToWindow(parent, kind, extra);
      } catch (e) {}

      try {
        var count = parent.length || 0;

        for (var i = 0; i < count; i++) {
          sendToWindow(parent.frames[i], kind, extra);
        }
      } catch (e) {
        // Some sandbox/browser combinations may block frame enumeration.
      }
    }

    function rememberPeer(data) {
      if (!data || data.ns !== NS) return;
      if (data.render_group_id !== RENDER_GROUP_ID) return;
      if (!data.instance_id || data.instance_id === INSTANCE_ID) return;

      peers[data.instance_id] = Object.assign({}, data, {
        last_seen: now()
      });
    }

    function candidateScore(c) {
      var score = 0;

      if (c.submitted) score += 1000000000000000;
      if (c.interacted) score += 1000000000;

      if (c.interacted && c.last_interaction_at) {
        score += c.last_interaction_at;
      } else {
        score += c.started_at || 0;
      }

      return score;
    }

    function getWinner() {
      cleanPeers();

      var candidates = [
        Object.assign({}, local, {
          interacted: interacted,
          submitted: submitted
        })
      ];

      Object.keys(peers).forEach(function (id) {
        candidates.push(peers[id]);
      });

      candidates.sort(function (a, b) {
        var scoreDiff = candidateScore(b) - candidateScore(a);

        if (scoreDiff !== 0) {
          return scoreDiff;
        }

        return String(b.instance_id).localeCompare(String(a.instance_id));
      });

      return candidates[0];
    }

    function setActive(value) {
      active = value;

      var app = document.getElementById("app");

      if (value) {
        document.documentElement.style.height = "";
        document.documentElement.style.overflow = "";
        document.body.style.height = "";
        document.body.style.minHeight = "";
        document.body.style.overflow = "";
        document.body.style.padding = "0";
        document.body.style.background = "transparent";

        if (app) {
          app.style.display = "";
        }

        reportHeight();
      } else {
        document.documentElement.style.height = "1px";
        document.documentElement.style.overflow = "hidden";
        document.body.style.height = "1px";
        document.body.style.minHeight = "1px";
        document.body.style.overflow = "hidden";
        document.body.style.padding = "0";
        document.body.style.background = "transparent";

        if (app) {
          app.style.display = "none";
        }

        parent.postMessage({ type: "iframe:height", height: 1 }, "*");
      }
    }

    function elect() {
      var winner = getWinner();
      var shouldBeActive = !winner || winner.instance_id === INSTANCE_ID;

      setActive(shouldBeActive);
    }

    function electSoon() {
      if (electionTimer) {
        clearTimeout(electionTimer);
      }

      electionTimer = setTimeout(elect, ELECTION_DELAY_MS);
    }

    function markInteracted() {
      if (submitted) return;

      interacted = true;

      updateLocal({
        interacted: true,
        last_interaction_at: now()
      });

      broadcast("interaction", {
        interacted: true,
        last_interaction_at: now()
      });

      electSoon();
    }

    window.addEventListener("message", function (event) {
      var data = event.data;

      if (!data || data.ns !== NS) return;
      if (data.render_group_id !== RENDER_GROUP_ID) return;
      if (data.instance_id === INSTANCE_ID) return;

      rememberPeer(data);

      if (data.kind === "hello") {
        sendToWindow(event.source, "ack");
      }

      if (data.kind === "submitted") {
        submitted = true;
        setActive(false);
      }

      electSoon();
    });

    document.addEventListener("input", markInteracted, true);
    document.addEventListener("change", markInteracted, true);
    document.addEventListener("keydown", markInteracted, true);

    document.addEventListener("click", function (event) {
      var target = event.target;

      if (
        target &&
        target.closest &&
        target.closest("button,input,label,textarea,.option-row")
      ) {
        markInteracted();
      }
    }, true);

    function start() {
      broadcast("hello");

      setTimeout(function () {
        broadcast("hello");
        elect();
      }, ELECTION_DELAY_MS);

      setTimeout(function () {
        broadcast("hello");
        elect();
      }, ELECTION_DELAY_MS * 2);

      setInterval(function () {
        broadcast("heartbeat");
        elect();
      }, HEARTBEAT_MS);
    }

    function markSubmitted() {
      submitted = true;

      updateLocal({
        submitted: true,
        interacted: true,
        last_interaction_at: now()
      });

      broadcast("submitted", {
        submitted: true,
        interacted: true,
        last_interaction_at: now()
      });
    }

    return {
      start: start,
      isActive: function () {
        return active;
      },
      markSubmitted: markSubmitted,
      markInteracted: markInteracted
    };
  }

  function showWarnings() {
    if (!WARNINGS.length) return;

    var banner = document.createElement("div");
    banner.className = "warning-banner";
    banner.textContent =
      t("warning_prefix", "⚠️ ") + WARNINGS.join(t("warning_joiner", " | "));

    var app = document.getElementById("app");
    app.insertBefore(banner, app.children[1]);
  }

  function clearValidation() {
    els.validation.textContent = "";
    els.validation.style.display = "none";
  }

  function showValidation(message) {
    els.validation.textContent = message;
    els.validation.style.display = "block";
    reportHeight();
  }

  function getAnswerValues(a) {
    var text = (a.text_value || "").trim();

    if (a.type === "text") {
      return text ? [text] : [];
    }

    var values = a.selected.slice();

    if (a.text_active && text) {
      values.push(text);
    }

    return values;
  }

  function answerForHuman(a) {
    var values = getAnswerValues(a);
    return values.length ? values.join(", ") : t("unanswered", "(unanswered)");
  }

  function validationMessage(a) {
    var values = getAnswerValues(a);

    if (a.type === "text") {
      var len = ((a.text_value || "").trim()).length;

      if (a.required && len === 0) {
        return t("validation_text_required", "Please enter an answer before continuing.");
      }

      if (a.min_length && len < a.min_length) {
        return fmt(
          "validation_text_min_length",
          "Please enter at least {min} character(s).",
          { min: a.min_length }
        );
      }

      if (a.max_length && len > a.max_length) {
        return fmt(
          "validation_text_max_length",
          "Please enter no more than {max} character(s).",
          { max: a.max_length }
        );
      }

      return "";
    }

    if (a.required && values.length === 0) {
      return t("validation_choice_required", "Please select an answer before continuing.");
    }

    if (a.type === "multiple" && a.min_selections && values.length < a.min_selections) {
      return fmt(
        "validation_multiple_min",
        "Please select at least {min} option(s).",
        { min: a.min_selections }
      );
    }

    if (a.type === "multiple" && a.max_selections && values.length > a.max_selections) {
      return fmt(
        "validation_multiple_max",
        "Please select no more than {max} option(s).",
        { max: a.max_selections }
      );
    }

    return "";
  }

  function firstInvalidIndex() {
    for (var i = 0; i < state.answers.length; i++) {
      if (validationMessage(state.answers[i])) {
        return i;
      }
    }

    return -1;
  }

  function metaText(q) {
    var parts = [];

    if (q.required) {
      parts.push(t("required_label", "Required"));
    } else {
      parts.push(t("optional_label", "Optional"));
    }

    if (q.type === "multiple") {
      if (q.min_selections && q.max_selections) {
        parts.push(fmt("select_range", "Select {min}-{max}", {
          min: q.min_selections,
          max: q.max_selections
        }));
      } else if (q.min_selections) {
        parts.push(fmt("select_at_least", "Select at least {min}", {
          min: q.min_selections
        }));
      } else if (q.max_selections) {
        parts.push(fmt("select_up_to", "Select up to {max}", {
          max: q.max_selections
        }));
      } else {
        parts.push(t("select_any", "Select any that apply"));
      }
    }

    if (q.type === "text") {
      if (q.min_length && q.max_length) {
        parts.push(fmt("characters_range", "{min}-{max} characters", {
          min: q.min_length,
          max: q.max_length
        }));
      } else if (q.min_length) {
        parts.push(fmt("characters_min", "At least {min} characters", {
          min: q.min_length
        }));
      } else if (q.max_length) {
        parts.push(fmt("characters_max", "Up to {max} characters", {
          max: q.max_length
        }));
      }
    }

    return parts.join(t("meta_separator", " · "));
  }

  function buildOptions(q) {
    els.list.innerHTML = "";

    if (q.type === "text") {
      var ta = document.createElement("textarea");
      ta.className = "free-textarea";
      ta.placeholder = q.placeholder;
      ta.value = q.text_value;
      ta.rows = 3;

      if (q.max_length) {
        ta.maxLength = q.max_length;
      }

      ta.addEventListener("input", function (e) {
        q.text_value = e.target.value;
        clearValidation();

        if (duplicateGuard) {
          duplicateGuard.markInteracted();
        }

        reportHeight();
      });

      els.list.appendChild(ta);
      setTimeout(reportHeight, 0);
      return;
    }

    q.proposals.forEach(function (prop, i) {
      var id = "opt_" + state.idx + "_" + i;
      var wrapper = document.createElement("div");
      wrapper.className = "option-row";

      var input = document.createElement("input");
      input.type = q.type === "multiple" ? "checkbox" : "radio";
      input.name = "opt_" + state.idx;
      input.id = id;
      input.value = prop;

      if (q.type === "multiple") {
        input.checked = q.selected.indexOf(prop) !== -1;
      } else {
        input.checked = q.selected.length === 1 && q.selected[0] === prop;
      }

      input.addEventListener("change", function () {
        clearValidation();

        if (duplicateGuard) {
          duplicateGuard.markInteracted();
        }

        if (q.type === "multiple") {
          if (input.checked) {
            if (q.selected.indexOf(prop) === -1) {
              q.selected.push(prop);
            }
          } else {
            q.selected = q.selected.filter(function (v) {
              return v !== prop;
            });
          }
        } else {
          q.selected = [prop];
          q.text_active = false;
          render();
        }
      });

      var label = document.createElement("label");
      label.htmlFor = id;
      label.textContent = prop;

      wrapper.appendChild(input);
      wrapper.appendChild(label);
      els.list.appendChild(wrapper);
    });

    if (q.allow_text) {
      var ftId = "opt_" + state.idx + "_text";
      var ftWrapper = document.createElement("div");
      ftWrapper.className = "option-row free-text-row";

      var ftInput = document.createElement("input");
      ftInput.type = q.type === "multiple" ? "checkbox" : "radio";
      ftInput.name = "opt_" + state.idx;
      ftInput.id = ftId;
      ftInput.checked = q.text_active;

      ftInput.addEventListener("change", function () {
        clearValidation();

        if (duplicateGuard) {
          duplicateGuard.markInteracted();
        }

        if (ftInput.checked) {
          q.text_active = true;

          if (q.type === "single") {
            q.selected = [];
          }
        } else {
          q.text_active = false;
        }

        render();
      });

      var ftLabel = document.createElement("label");
      ftLabel.htmlFor = ftId;
      ftLabel.textContent = q.other_label || t("other_label", "Other:");

      var txt = document.createElement("input");
      txt.type = "text";
      txt.className = "free-text-input";
      txt.placeholder = q.other_placeholder || t("other_placeholder", "Type here...");
      txt.value = q.text_value;
      txt.disabled = !q.text_active;

      txt.addEventListener("input", function (e) {
        q.text_value = e.target.value;
        clearValidation();

        if (duplicateGuard) {
          duplicateGuard.markInteracted();
        }
      });

      ftWrapper.appendChild(ftInput);
      ftWrapper.appendChild(ftLabel);
      ftWrapper.appendChild(txt);
      els.list.appendChild(ftWrapper);
    }
  }

  function render() {
    if (state.frozen) return;

    var q = state.answers[state.idx];

    els.title.textContent = TITLE;

    if (DESC) {
      els.desc.textContent = DESC;
      els.desc.style.display = "";
    } else {
      els.desc.style.display = "none";
    }

    els.counter.textContent = (state.idx + 1) + " / " + TOTAL;
    els.qtitle.textContent = q.question;
    els.qmeta.textContent = metaText(q);
    els.bar.style.width = ((state.idx + 1) / TOTAL * 100) + "%";

    els.btnPrev.textContent = t("previous_label", "← Previous");
    els.btnNext.textContent = state.idx === TOTAL - 1 ? SUBMIT : t("next_label", "Next →");
    els.btnFinish.textContent = t("finish_now_label", "Finish now");

    els.btnPrev.style.visibility = state.idx === 0 ? "hidden" : "visible";

    clearValidation();
    buildOptions(q);
    reportHeight();
  }

  function prev() {
    if (state.idx > 0) {
      state.idx--;
      render();
    }
  }

  function next() {
    if (duplicateGuard && !duplicateGuard.isActive()) {
      return;
    }

    var msg = validationMessage(state.answers[state.idx]);

    if (msg) {
      showValidation(msg);
      return;
    }

    if (state.idx < TOTAL - 1) {
      state.idx++;
      render();
    } else {
      submit();
    }
  }

  function submit() {
    if (state.frozen) return;

    var badIndex = firstInvalidIndex();

    if (badIndex !== -1) {
      state.idx = badIndex;
      render();
      showValidation(validationMessage(state.answers[badIndex]));
      return;
    }

    if (duplicateGuard && !duplicateGuard.isActive()) {
      return;
    }

    if (duplicateGuard) {
      duplicateGuard.markSubmitted();
    }

    state.frozen = true;
    sessionStorage.setItem(SESSION_KEY, "1");

    var lines = state.answers.map(function (a, i) {
      return (
        (i + 1) +
        ". " +
        a.question +
        "\n   " +
        t("answer_arrow", "→") +
        " " +
        answerForHuman(a)
      );
    });

    var md = t("markdown_heading_prefix", "## 📝 Question Wizard: ") + TITLE + "\n\n";

    if (DESC) {
      md += "**" + DESC + "**\n\n";
    }

    md += lines.join("\n\n");
    md += "\n\n---\n";
    md += t("answers_submitted_footer", "*Answers submitted via Question Wizard*");

    parent.postMessage({ type: "input:prompt:submit", text: md }, "*");

    els.btnPrev.disabled = true;
    els.btnNext.disabled = true;
    els.btnFinish.disabled = true;
    els.list.style.pointerEvents = "none";
    els.list.style.opacity = "0.6";

    var confirmDiv = document.createElement("div");
    confirmDiv.className = "confirmation";
    confirmDiv.textContent = t("answers_submitted_confirmation", "✅ Answers submitted.");
    document.getElementById("app").appendChild(confirmDiv);

    reportHeight();
  }

  els.btnPrev.addEventListener("click", prev);
  els.btnNext.addEventListener("click", next);
  els.btnFinish.addEventListener("click", submit);

  window.addEventListener("load", reportHeight);

  if (window.ResizeObserver) {
    new ResizeObserver(reportHeight).observe(document.body);
  }

  duplicateGuard = installDuplicateRenderGuard();

  showWarnings();
  render();
  duplicateGuard.start();
})();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# OPEN WEBUI TOOL
# ---------------------------------------------------------------------------


class Tools:
    """Open WebUI tool for interactive questionnaires."""

    _lock = asyncio.Lock()
    _recent_lock = asyncio.Lock()
    _recent_calls = {}

    class Valves:
        pass

    def __init__(self):
        self.citation = False

    async def run_question_wizard(self, questions_json: str, __user__: dict = None):
        """Launch a visual interactive questionnaire inside an iframe.

        Call EXACTLY ONCE per turn.
        Types: single | multiple | text.
        Proposals: 2-4 for single/multiple.
        Constraints: 1-13 questions total.
        """
        user_key = "anonymous"

        if isinstance(__user__, dict):
            user_key = (
                __user__.get("id")
                or __user__.get("email")
                or __user__.get("name")
                or "anonymous"
            )

        try:
            parsed_for_hash = json.loads(questions_json)
            canonical_json = _canonical_json_for_hash(parsed_for_hash)
        except Exception:
            canonical_json = str(questions_json)

        fingerprint = hashlib.sha256(
            f"{user_key}:{canonical_json}".encode("utf-8")
        ).hexdigest()

        now = time.monotonic()

        async with self._recent_lock:
            expired = [
                key
                for key, timestamp in self._recent_calls.items()
                if now - timestamp > _DEDUPE_SECONDS
            ]

            for key in expired:
                del self._recent_calls[key]

            previous = self._recent_calls.get(fingerprint)

            if previous is not None and now - previous <= _DEDUPE_SECONDS:
                return _blank_duplicate_response()

            self._recent_calls[fingerprint] = now

        if self._lock.locked():
            return _txt("error_already_running")

        async with self._lock:
            return await self._run_wizard(questions_json)

    async def _run_wizard(self, questions_json: str):
        try:
            payload = json.loads(questions_json)
        except json.JSONDecodeError as e:
            return _txt("error_invalid_json", error=e)

        if isinstance(payload, list):
            payload = {"questions": payload}
        elif isinstance(payload, dict) and "question" in payload and "questions" not in payload:
            payload = {"questions": [payload]}

        if not isinstance(payload, dict):
            return _txt("error_root_not_object")

        questions = payload.get("questions")

        if not isinstance(questions, list) or not (1 <= len(questions) <= _MAX_QUESTIONS):
            return _txt("error_questions_array", max=_MAX_QUESTIONS)

        normalised = []
        warnings = []
        seen_ids = set()

        for idx, q in enumerate(questions):
            result = _validate_question(q, idx)

            if isinstance(result, str):
                return result

            if isinstance(result, tuple):
                question_obj = result[0]
                warnings.append(result[1])
            else:
                question_obj = result

            base_id = question_obj["id"]
            unique_id = base_id
            suffix = 2

            while unique_id in seen_ids:
                unique_id = f"{base_id}_{suffix}"
                suffix += 1

            if unique_id != base_id:
                warnings.append(
                    _txt("warning_duplicate_id", old=base_id, new=unique_id)
                )
                question_obj["id"] = unique_id

            seen_ids.add(unique_id)
            normalised.append(question_obj)

        config = {
            "title": _clean_string(payload.get("title"), ""),
            "description": _clean_string(payload.get("description"), ""),
            "submit_label": _clean_string(payload.get("submit_label"), _txt("submit_label")),
            "version": _VERSION,
            "questions": normalised,
            "warnings": warnings,
            "ui_text": _UI_TEXT,
        }

        form_fingerprint_json = _canonical_json_for_hash(
            {
                "title": config["title"],
                "description": config["description"],
                "questions": config["questions"],
            }
        )

        config["form_id"] = "qw_form_" + hashlib.sha256(
            form_fingerprint_json.encode("utf-8")
        ).hexdigest()[:24]

        config["render_group_id"] = "qw_render_" + secrets.token_hex(12)

        config_json = json.dumps(config, ensure_ascii=False, separators=(",", ":"))
        config_json = config_json.replace("<", "\\u003c")

        session_key = (
            "qw_sub_"
            + hashlib.sha256(config_json.encode("utf-8")).hexdigest()[:24]
        )

        html_content = (
            _HTML_TEMPLATE
            .replace("__CONFIG_JSON__", config_json)
            .replace("__SESSION_KEY__", session_key)
        )

        return HTMLResponse(
            content=html_content,
            headers={
                "Content-Disposition": "inline",
                "X-Question-Wizard-Version": _VERSION,
            },
        )
