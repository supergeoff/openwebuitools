"""
title: Question Wizard
author: supergeoff
version: 0.4.0
description: |
    Interactive visual questionnaire for Open WebUI.

    ⚠️ Call `run_question_wizard` EXACTLY ONCE per user request.
    Usage: json.dumps({"title": "...", "questions": [{"question": "...", "type": "single", "proposals": ["Oui", "Non"]}]})
    Types: single | multiple | text    |    Proposals: 2-4 for single/multiple, optional for text
    Constraints: 1–13 questions total.

    Depends: fastapi.responses.HTMLResponse
"""

import asyncio
import json

from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
_MAX_QUESTIONS = 13
_MAX_PROPOSALS = 4
_MIN_PROPOSALS = 2

_TYPE_ALIASES = {
    "single": "single",
    "single_choice": "single",
    "multiple": "multiple",
    "multi_choice": "multiple",
    "text": "text",
    "open": "text",
}


def _validate_question(q: dict, idx: int) -> dict | str:
    """Normalize and validate a single question. Returns the normalized dict or an error string."""
    if not isinstance(q.get("question"), str):
        return f"Error: Missing or invalid 'question' field in question {idx + 1}."

    q_type = _TYPE_ALIASES.get(q.get("type", "single"), "single")
    proposals = q.get("proposals", [])

    if q_type in ("single", "multiple"):
        if not isinstance(proposals, list) or not (
            _MIN_PROPOSALS <= len(proposals) <= _MAX_PROPOSALS
        ):
            return f"Error: single/multiple questions need {_MIN_PROPOSALS}–{_MAX_PROPOSALS} proposals (question {idx + 1})."
    elif isinstance(proposals, list) and len(proposals) > _MAX_PROPOSALS:
        return f"Error: At most {_MAX_PROPOSALS} proposals allowed (question {idx + 1})."

    return {
        "question": q["question"],
        "type": q_type,
        "proposals": list(proposals) if isinstance(proposals, list) else [],
        "allow_text": False if q_type == "text" else q.get("allow_text", True) is not False,
        "placeholder": q.get("placeholder", "Tapez votre réponse…") if q_type == "text" else "",
    }

# Inline HTML template — self-contained, no external file.
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Question Wizard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #fafafa; color: #000000; padding: 8px; line-height: 1.45; }
  #app { max-width: 720px; margin: 0 auto; background: #ffffff; border-radius: 10px; border: 1px solid #e0e0e0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
  #header { padding: 12px 16px; border-bottom: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: flex-start; }
  #wizard-title { font-size: 1rem; font-weight: 600; color: #000000; }
  #wizard-desc  { font-size: 0.85rem;  color: #666666; margin-top: 3px; }
  #wizard-counter { font-size: 0.8rem; color: #666666; background: #fafafa; padding: 3px 8px; border-radius: 10px; white-space: nowrap; margin-left: 10px; }
  #progress-track { height: 3px; background: #e0e0e0; width: 100%; }
  #progress-bar  { height: 100%; width: 0%; background: #000000; transition: width 0.3s ease; }
  #question-card { padding: 16px; }
  #question-title { font-size: 0.95rem; font-weight: 500; margin-bottom: 12px; color: #000000; }
  .option-row { display: flex; align-items: center; gap: 8px; padding: 8px 10px; margin-bottom: 6px; border-radius: 6px; border: 1px solid #e0e0e0; background: #fafafa; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
  .option-row:hover { border-color: #999999; background: #f0f0f0; }
  input[type="radio"], input[type="checkbox"] { cursor: pointer; accent-color: #000000; width: 18px; height: 18px; flex-shrink: 0; }
  .option-row label { cursor: pointer; font-size: 0.9rem; color: #333333; flex: 1; }
  .free-text-row { align-items: center; gap: 8px; }
  .free-text-row label { flex: 0 0 auto; font-size: 0.9rem; color: #333333; }
  .free-text-input { flex: 1; background: #ffffff; color: #000000; border: 1px solid #cccccc; border-radius: 6px; padding: 6px 8px; font-size: 0.9rem; outline: none; transition: border-color 0.15s; }
  .free-text-input:focus { border-color: #000000; }
  .free-text-input:disabled { opacity: 0.5; background: #f0f0f0; cursor: not-allowed; }
  .free-textarea { width: 100%; min-height: 80px; background: #ffffff; color: #000000; border: 1px solid #cccccc; border-radius: 6px; padding: 10px; font-size: 0.9rem; outline: none; resize: vertical; transition: border-color 0.15s; }
  .free-textarea:focus { border-color: #000000; box-shadow: 0 0 0 3px rgba(37,99,235,0.1); }
  #nav-controls { padding: 12px 16px; border-top: 1px solid #e0e0e0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  button { cursor: pointer; border: none; border-radius: 6px; padding: 8px 14px; font-size: 0.9rem; font-weight: 500; transition: background 0.15s, transform 0.05s; }
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
      ta.value = q.text_value; ta.rows = 3;
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
    """Open WebUI tool for interactive questionnaires."""
    _lock = asyncio.Lock()

    class Valves:
        pass

    def __init__(self):
        self.citation = False

    async def run_question_wizard(self, questions_json: str, __user__: dict = None):
        """Launch a visual interactive questionnaire inside an iframe.

        Call EXACTLY ONCE per turn.
        Types: single | multiple | text    |    Proposals: 2-4 for single/multiple
        Constraints: 1-13 questions total.
        """
        async with self._lock:
            return await self._run_wizard(questions_json)

    async def _run_wizard(self, questions_json: str):
        try:
            payload = json.loads(questions_json)
        except json.JSONDecodeError as e:
            return f"Error: Invalid JSON -- {e}"

        if not isinstance(payload, dict):
            return "Error: The root element must be a JSON object."

        questions = payload.get("questions")
        if not isinstance(questions, list) or not (1 <= len(questions) <= _MAX_QUESTIONS):
            return f"Error: 'questions' must be an array with 1-{_MAX_QUESTIONS} items."

        normalized = []
        for idx, q in enumerate(questions):
            result = _validate_question(q, idx)
            if isinstance(result, str):
                return result
            normalized.append(result)

        config = {
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "submit_label": payload.get("submit_label", "Envoyer"),
            "questions": normalized,
        }

        # Escape '<' so the JSON never breaks out of the </script> tag.
        config_json = json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")

        return (
            HTMLResponse(content=_HTML_TEMPLATE.replace("__CONFIG_JSON__", config_json),
                        headers={"Content-Disposition": "inline"}),
            {"status": "question_wizard_active", "questions_count": len(config["questions"])},
        )
