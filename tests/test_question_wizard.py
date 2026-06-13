import importlib
import json
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


question_wizard = importlib.import_module("tools.question_wizard")


class QuestionWizardValidationTests(unittest.TestCase):
    def test_validate_question_supports_required_limits_ids_and_labels(self):
        result = question_wizard._validate_question(
            {
                "key": " priority / scope ",
                "question": "  Which priorities matter?  ",
                "type": "multiple",
                "options": ["Speed", "", "Quality", "Cost"],
                "required": "yes",
                "allow_text": "true",
                "other_label": "Custom:",
                "other_placeholder": "Type another priority",
                "min_selections": "2",
                "max_selections": "3",
            },
            0,
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], "priority_scope")
        self.assertEqual(result["question"], "Which priorities matter?")
        self.assertEqual(result["proposals"], ["Speed", "Quality", "Cost"])
        self.assertTrue(result["required"])
        self.assertEqual(result["other_label"], "Custom:")
        self.assertEqual(result["other_placeholder"], "Type another priority")
        self.assertEqual(result["min_selections"], 2)
        self.assertEqual(result["max_selections"], 3)

    def test_validate_text_question_supports_length_constraints(self):
        result = question_wizard._validate_question(
            {
                "name": "summary",
                "question": "Summarize the goal",
                "type": "text",
                "required": True,
                "min_length": "10",
                "max_length": "120",
            },
            0,
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result["id"], "summary")
        self.assertTrue(result["required"])
        self.assertEqual(result["min_length"], 10)
        self.assertEqual(result["max_length"], 120)


class QuestionWizardResponseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tools = question_wizard.Tools
        tools._recent_calls = {}
        if tools._lock.locked():
            self.skipTest("Question Wizard lock is unexpectedly held.")
        self.tool = tools()

    async def test_run_wizard_returns_html_response_with_english_ui_and_neutral_theme(self):
        payload = {
            "title": "Feedback",
            "questions": [
                {
                    "id": "priority",
                    "question": "Choose one",
                    "type": "single",
                    "proposals": ["A", "B"],
                    "required": True,
                }
            ],
        }

        response = await self.tool._run_wizard(json.dumps(payload))

        self.assertIsInstance(response, HTMLResponse)
        self.assertEqual(response.headers["x-question-wizard-version"], "0.6.5")

        html = response.body.decode("utf-8")
        self.assertIn('"submit_label":"Submit"', html)
        self.assertIn('"required_label":"Required"', html)
        self.assertIn("--qw-primary-bg: #000000;", html)
        self.assertIn("--qw-primary-bg: #ffffff;", html)
        self.assertNotIn("#6366f1", html)
        self.assertNotIn("#818cf8", html)

    async def test_run_question_wizard_dedupes_identical_calls_for_same_user(self):
        payload = json.dumps(
            {
                "title": "Feedback",
                "questions": [
                    {
                        "question": "Choose one",
                        "type": "single",
                        "proposals": ["A", "B"],
                    }
                ],
            }
        )

        first = await self.tool.run_question_wizard(payload, {"id": "user-1"})
        second = await self.tool.run_question_wizard(payload, {"id": "user-1"})

        self.assertIsInstance(first, HTMLResponse)
        self.assertIsInstance(second, HTMLResponse)
        self.assertIn("question_wizard_duplicate_guard_v1", first.body.decode("utf-8"))
        self.assertNotIn("question_wizard_duplicate_guard_v1", second.body.decode("utf-8"))
        self.assertRegex(second.body.decode("utf-8"), r"height:\s*1px")


if __name__ == "__main__":
    unittest.main()
