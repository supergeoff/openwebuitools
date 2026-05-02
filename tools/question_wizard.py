"""
title: Question Wizard
author: supergeoff
version: 0.3.0
description: |
    Interactive visual questionnaire for Open WebUI.

    ⚠️ CALL RULE: Call `run_question_wizard` **EXACTLY ONCE** per user request.
    Never call it a second time, never parallelize it. One call = one questionnaire.

    USAGE: Pass a JSON **string** (not an object, not an array) as the sole argument.

    JSON FORMAT — Root MUST be a JSON object `{...}`, NEVER an array `[...]`.
    Build the JSON like this in Python:

        json.dumps({
            "title": "My Questionnaire",        # optional string
            "description": "Context text",       # optional string
            "submit_label": "Envoyer",           # optional, default "Envoyer"
            "questions": [                        # REQUIRED array with 1-13 items
                {
                    "question": "Votre question ici ?",  # REQUIRED string
                    "type": "single",                    # "single" | "multiple" | "text"
                    "proposals": ["Oui", "Non"],         # REQUIRED for single/multiple: 2-4 strings
                    "allow_text": true                   # optional bool (default true for single/multiple)
                },
                {
                    "question": "Commentaire libre ?",
                    "type": "text",
                    "placeholder": "Écrivez ici..."      # optional for text type
                }
            ]
        })

    KEY RULES (strict, no synonyms):
    - Root: MUST be `{}` object — never start with `[`
    - `"questions"`: REQUIRED array at root level
    - `"question"`: REQUIRED string inside each question object
    - `"type"`: one of `"single"`, `"multiple"`, `"text"`
    - `"proposals"`: REQUIRED 2-4 strings for "single"/"multiple"; optional for "text"
    - NEVER use keys like "options", "choices", "answers"

    FULL EXAMPLE (copy-paste this pattern):
    {"title":"Sondage","description":"Feedback rapide","submit_label":"Envoyer","questions":[{"question":"Êtes-vous satisfait ?","type":"single","proposals":["Oui","Non","Mitigé"],"allow_text":true},{"question":"Commentaires ?","type":"text","placeholder":"Votre avis..."}]}

    Constraints:
    - 1 to 13 questions total
    - single/multiple MUST have 2 to 4 proposals
    - text needs no proposals (placeholder optional)

    Depends : fastapi.responses.HTMLResponse
"""

import json

from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
MAX_QUESTIONS = 13
MAX_PROPOSALS = 4
MIN_PROPOSALS = 2

# Inline HTML template — self-contained, no external file.
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Question Wizard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #fafafa; color: #000000; padding: 16px; line-height: 1.5; }
  #app { max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  #header { padding: 20px 24px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: flex-start; }
  #wizard-title { font-size: 1.15rem; font-weight: 600; color: #000000; }
  #wizard-desc  { font-size: 0.9rem;  color: #666666; margin-top: 4px; }
  #wizard-counter { font-size: 0.85rem; color: #666666; background: #fafafa; padding: 4px 10px; border-radius: 12px; white-space: nowrap; margin-left: 12px; }
  #progress-track { height: 4px; background: #e0e0e0; width: 100%; }
  #progress-bar  { height: 100%; width: 0%; background: #000000; transition: width 0.3s ease; }
  #question-card { padding: 24px; }
  #question-title { font-size: 1.05rem; font-weight: 500; margin-bottom: 16px; color: #000000; }
  .option-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; margin-bottom: 8px; border-radius: 8px; border: 1px solid #e0e0e0; background: #fafafa; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
  .option-row:hover { border-color: #999999; background: #f0f0f0; }
  input[type="radio"], input[type="checkbox"] { cursor: pointer; accent-color: #000000; width: 18px; height: 18px; flex-shrink: 0; }
  .option-row label { cursor: pointer; font-size: 0.95rem; color: #333333; flex: 1; }
  .free-text-row { align-items: center; gap: 10px; }
  .free-text-row label { flex: 0 0 auto; font-size: 0.95rem; color: #333333; }
  .free-text-input { flex: 1; background: #ffffff; color: #000000; border: 1px solid #cccccc; border-radius: 6px; padding: 6px 10px; font-size: 0.95rem; outline: none; transition: border-color 0.15s; }
  .free-text-input:focus { border-color: #000000; }
  .free-text-input:disabled { opacity: 0.5; background: #f0f0f0; cursor: not-allowed; }
  .free-textarea { width: 100%; min-height: 100px; background: #ffffff; color: #000000; border: 1px solid #cccccc; border-radius: 8px; padding: 12px; font-size: 0.95rem; outline: none; resize: vertical; transition: border-color 0.15s; }
  .free-textarea:focus { border-color: #000000; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
  #nav-controls { padding: 16px 24px; border-top: 1px solid #e0e0e0; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  button { cursor: pointer; border: none; border-radius: 8px; padding: 10px 18px; font-size: 0.95rem; font-weight: 500; transition: background 0.15s, transform 0.05s; }
  button:active { transform: translateY(1px); }
  #btn-prev { background: #f0f0f0; color: #333333; }
  #btn-prev:hover:not(:disabled) { background: #e0e0e0; }
  #btn-next { background: #000000; color: #ffffff; margin-left: auto; }
  #btn-next:hover:not(:disabled) { background: #333333; }
  #btn-skip { background: transparent; color: #666666; border: 1px solid #cccccc; }
  #btn-skip:hover:not(:disabled) { color: #333333; border-color: #9ca3af; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
  .confirmation { padding: 16px 24px; text-align: center; color: #000000; font-weight: 600; border-top: 1px solid #e0e0e0; background: #f5f5f5; }
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
    <div id="options-list"></div>
  </div>
  <div id="nav-controls">
    <button id="btn-prev">← Précédent</button>
    <button id="btn-skip">Sauter le reste</button>
    <button id="btn-next">Suivant →</button>
  </div>
</div>
<script id="wizard-config" type="application/json">__CONFIG_JSON__</script>
<script>
(function () {
  "use strict";
  var CONFIG = JSON.parse(document.getElementById("wizard-config").textContent);
  var TOTAL  = CONFIG.questions.length;
  var TITLE  = CONFIG.title || "Question Wizard";
  var DESC   = CONFIG.description || "";
  var SUBMIT = CONFIG.submit_label || "Envoyer";
  var state = { idx: 0, frozen: false,
    answers: CONFIG.questions.map(function (q) {
      var isText = q.type === "text";
      return { question: q.question,
        type: isText ? "text" : (q.type === "multiple" ? "multiple" : "single"),
        proposals:   q.proposals || [],
        allow_text:  isText ? false : (q.allow_text !== false),
        placeholder: q.placeholder || "Tapez votre réponse…",
        selected:    [], text_active: false, text_value: "" };
    }) };
  var els = {
    title:   document.getElementById("wizard-title"),
    desc:    document.getElementById("wizard-desc"),
    counter: document.getElementById("wizard-counter"),
    qtitle:  document.getElementById("question-title"),
    list:    document.getElementById("options-list"),
    btnPrev: document.getElementById("btn-prev"),
    btnNext: document.getElementById("btn-next"),
    btnSkip: document.getElementById("btn-skip"),
    bar:     document.getElementById("progress-bar") };
  function reportHeight() {
    var h = document.documentElement.scrollHeight;
    parent.postMessage({ type: "iframe:height", height: h }, "*"); }
  function buildOptions(q) {
    els.list.innerHTML = "";
    if (q.type === "text") {
      var ta = document.createElement("textarea");
      ta.className = "free-textarea"; ta.placeholder = q.placeholder;
      ta.value = q.text_value; ta.rows = 4;
      ta.addEventListener("input", function (e) { q.text_value = e.target.value; reportHeight(); });
      els.list.appendChild(ta); setTimeout(reportHeight, 0); return; }
    q.proposals.forEach(function (prop, i) {
      var id = "opt_" + state.idx + "_" + i;
      var wrapper = document.createElement("div"); wrapper.className = "option-row";
      var input = document.createElement("input");
      input.type = q.type === "multiple" ? "checkbox" : "radio";
      input.name = "opt_" + state.idx; input.id = id; input.value = prop;
      if (q.type === "multiple") { input.checked = q.selected.indexOf(prop) !== -1; }
      else { input.checked = q.selected.length === 1 && q.selected[0] === prop; }
      input.addEventListener("change", function () {
        if (q.type === "multiple") {
          if (input.checked) { if (q.selected.indexOf(prop) === -1) q.selected.push(prop); }
          else { q.selected = q.selected.filter(function (v) { return v !== prop; }); }
        } else { q.selected = [prop]; q.text_active = false; render(); }
      });
      var label = document.createElement("label"); label.htmlFor = id; label.textContent = prop;
      wrapper.appendChild(input); wrapper.appendChild(label); els.list.appendChild(wrapper);
    });
    if (q.allow_text) {
      var ftId = "opt_" + state.idx + "_text";
      var wrapper = document.createElement("div"); wrapper.className = "option-row free-text-row";
      var input = document.createElement("input");
      input.type = q.type === "multiple" ? "checkbox" : "radio";
      input.name = "opt_" + state.idx; input.id = ftId; input.checked = q.text_active;
      input.addEventListener("change", function () {
        if (input.checked) { q.text_active = true; if (q.type === "single") q.selected = []; }
        else { q.text_active = false; } render(); });
      var lbl = document.createElement("label"); lbl.htmlFor = ftId; lbl.textContent = "Autre :";
      var txt = document.createElement("input"); txt.type = "text"; txt.className = "free-text-input";
      txt.placeholder = "Tapez ici…"; txt.value = q.text_value; txt.disabled = !q.text_active;
      txt.addEventListener("input", function (e) { q.text_value = e.target.value; });
      wrapper.appendChild(input); wrapper.appendChild(lbl); wrapper.appendChild(txt);
      els.list.appendChild(wrapper); } }
  function render() {
    if (state.frozen) return; var q = state.answers[state.idx];
    els.title.textContent = TITLE;
    if (DESC) { els.desc.textContent = DESC; els.desc.style.display = ""; }
    else { els.desc.style.display = "none"; }
    els.counter.textContent = (state.idx + 1) + " / " + TOTAL;
    els.qtitle.textContent = q.question; els.bar.style.width = ((state.idx + 1) / TOTAL * 100) + "%";
    els.btnPrev.style.visibility = state.idx === 0 ? "hidden" : "visible";
    els.btnNext.textContent = state.idx === TOTAL - 1 ? SUBMIT : "Suivant →";
    buildOptions(q); reportHeight(); }
  function prev() { if (state.idx > 0) { state.idx--; render(); } }
  function next() { if (state.idx < TOTAL - 1) { state.idx++; render(); } else { submit(); } }
  function submit() {
    if (state.frozen) return; state.frozen = true;
    var lines = state.answers.map(function (a, i) {
      var ans; if (a.type === "text") { var v = a.text_value ? a.text_value.trim() : ""; ans = v || "(non répondu)"; }
      else { var parts = []; parts = parts.concat(a.selected); if (a.text_active && a.text_value !== "") parts.push(a.text_value);
        ans = parts.length ? parts.join(", ") : "(non répondu)"; }
      return (i + 1) + ". " + a.question + "\n   → " + ans; });
    var md = "## 📝 Question Wizard: " + TITLE + "\n\n";
    if (DESC) { md += "**" + DESC + "**\n\n"; }
    md += lines.join("\n\n"); md += "\n\n---\n*Answers submitted via Question Wizard*";
    parent.postMessage({ type: "input:prompt:submit", text: md }, "*");
    els.btnPrev.disabled = true; els.btnNext.disabled = true; els.btnSkip.disabled = true;
    els.list.style.pointerEvents = "none"; els.list.style.opacity = "0.6";
    var confirmDiv = document.createElement("div"); confirmDiv.className = "confirmation";
    confirmDiv.textContent = "\u2705 R\u00e9ponses envoy\u00e9es !";
    document.getElementById("app").appendChild(confirmDiv); reportHeight(); }
  els.btnPrev.addEventListener("click", prev); els.btnNext.addEventListener("click", next); els.btnSkip.addEventListener("click", submit);
  window.addEventListener("load", reportHeight); new ResizeObserver(reportHeight).observe(document.body); render();
})();
</script>
</body>
</html>"""


class Tools:
    # Class-level lock prevents parallel/double calls within the same process.
    _is_running: bool = False

    class Valves:
        """Open WebUI Valves (no configuration required)."""
        pass

    def __init__(self):
        self.citation = False

    # -----------------------------------------------------------------------
    # PUBLIC TOOL METHOD
    # -----------------------------------------------------------------------
    async def run_question_wizard(self, questions_json: str, __user__: dict = None):
        """
        Launch a visual interactive questionnaire inside an iframe.

        ⚠️ IMPORTANT: Call this function EXACTLY ONCE per turn. Do NOT call it multiple
        times in the same response.

        Question types:
        - "single"  / "single_choice"  -> pick one radio option.
        - "multiple" / "multi_choice" -> pick many checkboxes.
        - "text"    / "open"          -> free-form textarea (no proposals needed).

        Constraints:
        - 1 to 13 questions total.
        - single/multiple MUST have exactly 2 to 4 proposals.
        - text/open needs no proposals.

        :param questions_json: JSON string describing the questionnaire.
        :param __user__: Open WebUI injected user context dict.
        :return: (HTMLResponse, context_dict) or plain error string on failure.
        """
        # --- Guard: prevent double / parallel execution -------------------
        if Tools._is_running:
            return "Error: Question Wizard is already running. Please wait for the current wizard to finish before starting a new one."
        Tools._is_running = True

        try:
            return await self._run_wizard(questions_json)
        finally:
            Tools._is_running = False

    async def _run_wizard(self, questions_json: str):
        """Core logic — called with the lock already held."""
        # --- Parse JSON ----------------------------------------------------
        try:
            payload = json.loads(questions_json)
        except Exception:
            return "Error: Invalid JSON. Please check the syntax of questions_json."

        if not isinstance(payload, dict):
            return "Error: Invalid JSON. The root element must be an object."

        questions = payload.get("questions")
        if not isinstance(questions, list):
            return "Error: The JSON must contain a 'questions' array."

        if not (1 <= len(questions) <= MAX_QUESTIONS):
            return (
                f"Error: The questionnaire must contain between 1 and "
                f"{MAX_QUESTIONS} questions."
            )

        # --- Validate & normalise each question ----------------------------
        normalized = []
        for idx, q in enumerate(questions):
            if not isinstance(q, dict):
                return f"Error: Question {idx + 1} is not a valid object."

            if "question" not in q or not isinstance(q["question"], str):
                return (
                    f"Error: Missing or invalid 'question' field in question "
                    f"{idx + 1}."
                )

            # Normalise type aliases
            raw_type = q.get("type", "single")
            if raw_type in ("single", "single_choice"):
                q_type = "single"
            elif raw_type in ("multiple", "multi_choice"):
                q_type = "multiple"
            elif raw_type in ("text", "open"):
                q_type = "text"
            else:
                q_type = "single"

            proposals = q.get("proposals", [])

            # Validate proposal counts per type
            if q_type in ("single", "multiple"):
                if not isinstance(proposals, list) or not (
                    MIN_PROPOSALS <= len(proposals) <= MAX_PROPOSALS
                ):
                    return (
                        f"Error: Each single/multiple question must have between "
                        f"{MIN_PROPOSALS} and {MAX_PROPOSALS} proposals. "
                        f"(question {idx + 1})"
                    )
            else:
                # text/open: proposals are optional, but max 4 if present
                if isinstance(proposals, list) and len(proposals) > MAX_PROPOSALS:
                    return (
                        f"Error: At most {MAX_PROPOSALS} proposals even for "
                        f"text questions. (question {idx + 1})"
                    )

            # allow_text only makes sense for single / multiple
            allow_text = (
                False
                if q_type == "text"
                else (q.get("allow_text", True) is not False)
            )

            normalized.append(
                {
                    "question": q["question"],
                    "type": q_type,
                    "proposals": list(proposals) if isinstance(proposals, list) else [],
                    "allow_text": allow_text,
                    "placeholder": (
                        q.get("placeholder", "Tapez votre réponse…")
                        if q_type == "text"
                        else ""
                    ),
                }
            )

        # --- Assemble config dict for the frontend -------------------------
        config = {
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "submit_label": payload.get("submit_label", "Envoyer"),
            "questions": normalized,
        }

        # Serialise with raw unicode, then escape '<' so the JSON never
        # breaks out of the </script> tag in the HTML template.
        config_json = json.dumps(config, ensure_ascii=False, separators=((",", ":")))
        config_json = config_json.replace("<", "\\u003c")

        # --- Build response ------------------------------------------------
        html_content = _HTML_TEMPLATE.replace("__CONFIG_JSON__", config_json)

        return (
            HTMLResponse(
                content=html_content,
                headers={"Content-Disposition": "inline"},
            ),
            {
                "status": "question_wizard_active",
                "questions_count": len(config["questions"]),
            },
        )
