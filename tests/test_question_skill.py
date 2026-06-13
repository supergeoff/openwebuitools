from pathlib import Path
import sys
import types
import unittest

try:
    from fastapi.responses import HTMLResponse
except ModuleNotFoundError:
    fastapi_module = types.ModuleType("fastapi")
    responses_module = types.ModuleType("fastapi.responses")

    class HTMLResponse:
        def __init__(self, content="", headers=None):
            self.body = content.encode("utf-8")
            self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    responses_module.HTMLResponse = HTMLResponse
    sys.modules["fastapi"] = fastapi_module
    sys.modules["fastapi.responses"] = responses_module

from tools import question_wizard


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "question" / "SKILL.md"


class QuestionSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_text = SKILL_PATH.read_text(encoding="utf-8")

    def test_skill_matches_current_question_wizard_contract(self):
        expected_snippets = [
            f"version {question_wizard._VERSION}",
            "default `\"Submit\"`",
            "`id`",
            "`required`",
            "`other_label`",
            "`other_placeholder`",
            "`min_selections`",
            "`max_selections`",
            "`min_length`",
            "`max_length`",
            "`key` and `name`",
            f"{question_wizard._DEDUPE_SECONDS} seconds",
            "duplicate identical calls",
            "blank 1px response",
            "canonical shape",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.skill_text)

    def test_skill_no_longer_documents_old_french_default_submit_label(self):
        self.assertNotIn('default "Envoyer"', self.skill_text)


if __name__ == "__main__":
    unittest.main()
