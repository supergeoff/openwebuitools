"""
title: Question Wizard
author: supergeoff
version: 0.1.0
description: |
    Displays an interactive visual questionnaire inside an iframe.
    Supports single and multiple choice questions with optional free text.
    The user navigates, selects answers, then submits them back to the LLM
    as a formatted markdown message via postMessage injection.
    *All UI labels are in French; all code and docstrings are in English.*
"""

import html
import json

from fastapi.responses import HTMLResponse


class Tools:
    class Valves:
        """Open WebUI Valves (no configuration required)."""

        pass

    def __init__(self):
        self.citation = False

    def _generate_html(self, config: dict) -> str:
        """
        Generate a complete single-page HTML wizard from the parsed config dict.

        :param config: validated configuration dictionary with questions metadata.
        :return: full HTML string ready for HTMLResponse.
        """
        # Serialize config and escape '<' to avoid premature </script> tags
        config_json = json.dumps(config, ensure_ascii=False).replace("<", "\\u003c")

        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"fr\">",
            "<head>",
            "<meta charset=\"UTF-8\">",
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            "<title>Question Wizard</title>",
            "<style>",
            "* { box-sizing: border-box; margin: 0; padding: 0; }",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #1e1e2e; color: #cdd6f4; padding: 16px; line-height: 1.5; }",
            "#app { max-width: 640px; margin: 0 auto; background: #2a2a3c; border-radius: 12px; border: 1px solid #45475a; overflow: hidden; }",
            "#header { padding: 20px 24px; border-bottom: 1px solid #45475a; display: flex; justify-content: space-between; align-items: center; }",
            "#wizard-title { font-size: 1.15rem; font-weight: 600; color: #cdd6f4; }",
            "#wizard-desc { font-size: 0.9rem; color: #a6adc8; margin-top: 4px; }",
            "#wizard-counter { font-size: 0.85rem; color: #a6adc8; background: #313244; padding: 4px 10px; border-radius: 12px; white-space: nowrap; }",
            "#progress-track { height: 4px; background: #313244; width: 100%; }",
            "#progress-bar { height: 100%; width: 0%; background: #89b4fa; transition: width 0.3s ease; }",
            "#question-card { padding: 24px; }",
            "#question-title { font-size: 1.05rem; font-weight: 500; margin-bottom: 16px; color: #cdd6f4; }",
            ".option-row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; margin-bottom: 8px; border-radius: 8px; border: 1px solid #45475a; background: #313244; cursor: pointer; transition: border-color 0.15s, background 0.15s; }",
            ".option-row:hover { border-color: #585b70; background: #3b3b52; }",
            "input[type=\"radio\"], input[type=\"checkbox\"] { cursor: pointer; accent-color: #89b4fa; width: 18px; height: 18px; flex-shrink: 0; }",
            ".option-row label { cursor: pointer; font-size: 0.95rem; color: #cdd6f4; flex: 1; }",
            ".free-text-row { align-items: center; gap: 10px; }",
            ".free-text-row label { flex: 0 0 auto; }",
            ".free-text-input { flex: 1; background: #1e1e2e; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 10px; font-size: 0.95rem; outline: none; transition: border-color 0.15s; }",
            ".free-text-input:focus { border-color: #89b4fa; }",
            ".free-text-input:disabled { opacity: 0.5; cursor: not-allowed; }",
            "#nav-controls { padding: 16px 24px; border-top: 1px solid #45475a; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }",
            "button { cursor: pointer; border: none; border-radius: 8px; padding: 10px 18px; font-size: 0.95rem; font-weight: 500; transition: background 0.15s, transform 0.05s; }",
            "button:active { transform: translateY(1px); }",
            "#btn-prev { background: #45475a; color: #cdd6f4; }",
            "#btn-prev:hover:not(:disabled) { background: #585b70; }",
            "#btn-next { background: #89b4fa; color: #1e1e2e; margin-left: auto; }",
            "#btn-next:hover:not(:disabled) { background: #b4befe; }",
            "#btn-skip { background: transparent; color: #a6adc8; border: 1px solid #45475a; }",
            "#btn-skip:hover:not(:disabled) { color: #cdd6f4; border-color: #585b70; }",
            "button:disabled { opacity: 0.4; cursor: not-allowed; }",
            ".confirmation { padding: 16px 24px; text-align: center; color: #a6e3a1; font-weight: 600; border-top: 1px solid #45475a; }",
            "</style>",
            "</head>",
            "<body>",
            "<div id=\"app\">",
            "  <div id=\"header\">",
            "    <div>",
            "      <div id=\"wizard-title\"></div>",
            "      <div id=\"wizard-desc\"></div>",
            "    </div>",
            "    <div id=\"wizard-counter\"></div>",
            "  </div>",
            "  <div id=\"progress-track\"><div id=\"progress-bar\"></div></div>",
            "  <div id=\"question-card\">",
            "    <h2 id=\"question-title\"></h2>",
            "    <div id=\"options-list\"></div>",
            "  </div>",
            "  <div id=\"nav-controls\">",
            "    <button id=\"btn-prev\">← Précédent</button>",
            "    <button id=\"btn-skip\">Skip le reste</button>",
            "    <button id=\"btn-next\">Suivant →</button>",
            "  </div>",
            "</div>",
            "<script id=\"wizard-config\" type=\"application/json\">" + config_json + "</script>",
            "<script>",
            "(function () {",
            "  var CONFIG = JSON.parse(document.getElementById('wizard-config').textContent);",
            "  var TOTAL = CONFIG.questions.length;",
            "  var TITLE = CONFIG.title || 'Questions';",
            "  var DESC = CONFIG.description || '';",
            "  var SUBMIT_LABEL = CONFIG.submit_label || 'Envoyer';",
            "",
            "  var state = {",
            "    idx: 0,",
            "    answers: CONFIG.questions.map(function (q) {",
            "      return {",
            "        question: q.question,",
            "        type: q.type === 'multiple' ? 'multiple' : 'single',",
            "        proposals: q.proposals,",
            "        allow_text: q.allow_text !== false,",
            "        selected: [],",
            "        text_active: false,",
            "        text_value: ''",
            "      };",
            "    })",
            "  };",
            "",
            "  var els = {",
            "    title: document.getElementById('wizard-title'),",
            "    desc: document.getElementById('wizard-desc'),",
            "    counter: document.getElementById('wizard-counter'),",
            "    questionTitle: document.getElementById('question-title'),",
            "    optionsList: document.getElementById('options-list'),",
            "    btnPrev: document.getElementById('btn-prev'),",
            "    btnNext: document.getElementById('btn-next'),",
            "    btnSkip: document.getElementById('btn-skip'),",
            "    progressBar: document.getElementById('progress-bar')",
            "  };",
            "",
            "  function reportHeight () {",
            "    var h = document.documentElement.scrollHeight;",
            "    parent.postMessage({ type: 'iframe:height', height: h }, '*');",
            "  }",
            "",
            "  function buildOptions (q) {",
            "    els.optionsList.innerHTML = '';",
            "    q.proposals.forEach(function (prop, i) {",
            "      var id = 'opt_' + state.idx + '_' + i;",
            "      var wrapper = document.createElement('div');",
            "      wrapper.className = 'option-row';",
            "",
            "      var input = document.createElement('input');",
            "      input.type = q.type === 'multiple' ? 'checkbox' : 'radio';",
            "      input.name = 'opt_' + state.idx;",
            "      input.id = id;",
            "      input.value = prop;",
            "      if (q.type === 'multiple') {",
            "        input.checked = q.selected.indexOf(prop) !== -1;",
            "      } else {",
            "        input.checked = q.selected.length === 1 && q.selected[0] === prop;",
            "      }",
            "",
            "      input.addEventListener('change', function () {",
            "        if (q.type === 'multiple') {",
            "          if (input.checked) {",
            "            if (q.selected.indexOf(prop) === -1) q.selected.push(prop);",
            "          } else {",
            "            q.selected = q.selected.filter(function (v) { return v !== prop; });",
            "          }",
            "        } else {",
            "          q.selected = [prop];",
            "          q.text_active = false;",
            "          render();",
            "        }",
            "      });",
            "",
            "      var label = document.createElement('label');",
            "      label.htmlFor = id;",
            "      label.textContent = prop;",
            "",
            "      wrapper.appendChild(input);",
            "      wrapper.appendChild(label);",
            "      els.optionsList.appendChild(wrapper);",
            "    });",
            "",
            "    if (q.allow_text) {",
            "      var ftId = 'opt_' + state.idx + '_text';",
            "      var wrapper = document.createElement('div');",
            "      wrapper.className = 'option-row free-text-row';",
            "",
            "      var input = document.createElement('input');",
            "      input.type = q.type === 'multiple' ? 'checkbox' : 'radio';",
            "      input.name = 'opt_' + state.idx;",
            "      input.id = ftId;",
            "      input.checked = q.text_active;",
            "",
            "      input.addEventListener('change', function () {",
            "        if (input.checked) {",
            "          q.text_active = true;",
            "          if (q.type === 'single') {",
            "            q.selected = [];",
            "          }",
            "        } else {",
            "          q.text_active = false;",
            "        }",
            "        render();",
            "      });",
            "",
            "      var lbl = document.createElement('label');",
            "      lbl.htmlFor = ftId;",
            "      lbl.textContent = 'Autre :';",
            "",
            "      var txt = document.createElement('input');",
            "      txt.type = 'text';",
            "      txt.className = 'free-text-input';",
            "      txt.placeholder = 'Tapez votre réponse...';",
            "      txt.value = q.text_value;",
            "      txt.disabled = !q.text_active;",
            "      txt.addEventListener('input', function (e) {",
            "        q.text_value = e.target.value;",
            "      });",
            "",
            "      wrapper.appendChild(input);",
            "      wrapper.appendChild(lbl);",
            "      wrapper.appendChild(txt);",
            "      els.optionsList.appendChild(wrapper);",
            "    }",
            "  }",
            "",
            "  function render () {",
            "    var q = state.answers[state.idx];",
            "",
            "    els.title.textContent = TITLE;",
            "    if (DESC) {",
            "      els.desc.textContent = DESC;",
            "      els.desc.style.display = '';",
            "    } else {",
            "      els.desc.style.display = 'none';",
            "    }",
            "",
            "    els.counter.textContent = (state.idx + 1) + ' / ' + TOTAL;",
            "    els.questionTitle.textContent = q.question;",
            "    els.progressBar.style.width = ((state.idx + 1) / TOTAL * 100) + '%';",
            "",
            "    els.btnPrev.style.visibility = state.idx === 0 ? 'hidden' : 'visible';",
            "    if (state.idx === TOTAL - 1) {",
            "      els.btnNext.textContent = SUBMIT_LABEL;",
            "    } else {",
            "      els.btnNext.textContent = 'Suivant →';",
            "    }",
            "",
            "    buildOptions(q);",
            "    reportHeight();",
            "  }",
            "",
            "  function prev () {",
            "    if (state.idx > 0) {",
            "      state.idx--;",
            "      render();",
            "    }",
            "  }",
            "",
            "  function next () {",
            "    if (state.idx < TOTAL - 1) {",
            "      state.idx++;",
            "      render();",
            "    } else {",
            "      submit();",
            "    }",
            "  }",
            "",
            "  function submit () {",
            "    var lines = state.answers.map(function (a, i) {",
            "      var parts = [];",
            "      parts = parts.concat(a.selected);",
            "      if (a.text_active && a.text_value !== '') {",
            "        parts.push(a.text_value);",
            "      }",
            "      var ans = parts.length ? parts.join(', ') : '(non répondu)';",
            "      return (i + 1) + '. ' + a.question + '\\n   -> ' + ans;",
            "    });",
            "",
            "    var md = '## 📝 Questions: ' + TITLE + '\\n\\n';",
            "    if (DESC) {",
            "      md += '**' + DESC + '**\\n\\n';",
            "    }",
            "    md += lines.join('\\n\\n');",
            "    md += '\\n\\n---\\n*Answers submitted via Question Wizard*';",
            "",
            "    parent.postMessage({ type: 'input:prompt:submit', text: md }, '*');",
            "",
            "    els.btnPrev.disabled = true;",
            "    els.btnNext.disabled = true;",
            "    els.btnSkip.disabled = true;",
            "    els.optionsList.style.pointerEvents = 'none';",
            "    els.optionsList.style.opacity = '0.6';",
            "",
            "    var confirmDiv = document.createElement('div');",
            "    confirmDiv.className = 'confirmation';",
            "    confirmDiv.textContent = '✅ Réponses envoyées !';",
            "    document.getElementById('app').appendChild(confirmDiv);",
            "    reportHeight();",
            "  }",
            "",
            "  els.btnPrev.addEventListener('click', prev);",
            "  els.btnNext.addEventListener('click', next);",
            "  els.btnSkip.addEventListener('click', submit);",
            "",
            "  window.addEventListener('load', reportHeight);",
            "  new ResizeObserver(reportHeight).observe(document.body);",
            "",
            "  render();",
            "})();",
            "</script>",
            "</body>",
            "</html>",
        ]

        return "\n".join(html_parts)

    async def run_questionnaire(
        self, questions_json: str, __user__: dict = None
    ) -> tuple[HTMLResponse, dict] | str:
        """
        Launch a visual interactive questionnaire with question navigation.
        The user selects predefined proposals and/or types free text,
        then sends their answers back to the LLM via message injection.

        :param questions_json: JSON string describing the questionnaire.
            Expected format::

                {
                    "title": "string (optional)",
                    "description": "string (optional)",
                    "submit_label": "string (optional, default: 'Envoyer')",
                    "questions": [
                        {
                            "question": "string (required)",
                            "type": "single | multiple",
                            "proposals": ["string", "string", ...],
                            "allow_text": "bool (optional, default: true)"
                        }
                    ]
                }

        :param __user__: Open WebUI injected user context dict.
        :return: On success, a tuple (HTMLResponse, context_dict).
            On validation failure, a plain error string.
        """
        # ------------------------------------------------------------------
        # Input validation
        # ------------------------------------------------------------------
        try:
            payload = json.loads(questions_json)
        except Exception:
            return "Error: Invalid JSON. Please check the syntax of the questions_json parameter."

        if not isinstance(payload, dict):
            return "Error: Invalid JSON. The root element must be an object."

        questions = payload.get("questions")
        if not isinstance(questions, list):
            return "Error: The JSON must contain a 'questions' array."

        if not (1 <= len(questions) <= 13):
            return "Error: The questionnaire must contain between 1 and 13 questions."

        for idx, q in enumerate(questions):
            if not isinstance(q, dict):
                return f"Error: Question {idx + 1} is not a valid object."

            if "question" not in q or not isinstance(q["question"], str):
                return f"Error: Missing or invalid 'question' field in question {idx + 1}."

            proposals = q.get("proposals")
            if not isinstance(proposals, list) or len(proposals) < 2:
                return f"Error: Each question must have at least 2 proposals. (question {idx + 1})"

            # Normalize fields
            if q.get("type") not in ("single", "multiple"):
                q["type"] = "single"

            if "allow_text" not in q or not isinstance(q["allow_text"], bool):
                q["allow_text"] = True

        # ------------------------------------------------------------------
        # Build normalized config dict for the wizard
        # ------------------------------------------------------------------
        config = {
            "title": html.escape(payload.get("title", ""), quote=True),
            "description": html.escape(payload.get("description", ""), quote=True),
            "submit_label": html.escape(payload.get("submit_label", "Envoyer"), quote=True),
            "questions": [
                {
                    "question": html.escape(q["question"], quote=True),
                    "type": q["type"],
                    "proposals": [html.escape(p, quote=True) for p in q["proposals"]],
                    "allow_text": q["allow_text"],
                }
                for q in questions
            ],
        }

        html_content = self._generate_html(config)

        return (
            HTMLResponse(content=html_content, headers={"Content-Disposition": "inline"}),
            {"status": "questionnaire_active", "questions_count": len(config["questions"])},
        )
