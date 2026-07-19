import asyncio
import importlib.util
import inspect
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "actions" / "langfuse_feedback.py"


def load_action_module():
    if "pydantic" not in sys.modules:
        pydantic = types.ModuleType("pydantic")

        class BaseModel:
            def __init__(self, **values):
                for name in getattr(self, "__annotations__", {}):
                    setattr(self, name, values.get(name, getattr(self, name)))

        def Field(default=None, **kwargs):
            return default

        pydantic.BaseModel = BaseModel
        pydantic.Field = Field
        sys.modules["pydantic"] = pydantic

    spec = importlib.util.spec_from_file_location("langfuse_feedback", ACTION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_action(action, body, **kwargs):
    result = action.action(body, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def capture_scores(action, scores):
    async def _post_score(**kwargs):
        scores.append(kwargs)

    action._post_score = _post_score


class LangfuseFeedbackActionTest(unittest.TestCase):
    def test_trace_id_matches_system_filter_convention(self):
        module = load_action_module()
        action = module.Action()

        self.assertEqual(
            action._build_trace_id("chat-1", "msg-2"),
            "owui-chat-1-msg-2",
        )

    def test_positive_feedback_creates_numeric_and_category_scores(self):
        module = load_action_module()
        action = module.Action()
        action.valves.langfuse_public_key = "pk-test"
        action.valves.langfuse_secret_key = "sk-test"
        scores = []
        capture_scores(action, scores)

        events = []

        async def event_emitter(event):
            events.append(event)

        result = run_action(
            action,
            {"model": "gpt-test"},
            __id__="positive",
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
            __event_emitter__=event_emitter,
        )

        self.assertIsNone(result)
        self.assertEqual(len(scores), 2)
        self.assertEqual(scores[0]["trace_id"], "owui-chat-1-msg-1")
        self.assertEqual(scores[0]["name"], "owui_user_feedback")
        self.assertEqual(scores[0]["value"], 1.0)
        self.assertEqual(scores[0]["data_type"], "NUMERIC")
        self.assertEqual(
            scores[0]["score_id"],
            "owui:owui_user_feedback:positive:owui-chat-1-msg-1:user-1",
        )
        self.assertEqual(scores[1]["trace_id"], "owui-chat-1-msg-1")
        self.assertEqual(scores[1]["name"], "owui_feedback_category")
        self.assertEqual(scores[1]["value"], "positive")
        self.assertEqual(scores[1]["data_type"], "CATEGORICAL")
        self.assertEqual(events[-1]["data"]["type"], "success")

    def test_openwebui_action_payload_id_is_used_as_message_id(self):
        module = load_action_module()
        action = module.Action()
        action.valves.langfuse_public_key = "pk-test"
        action.valves.langfuse_secret_key = "sk-test"
        scores = []
        capture_scores(action, scores)

        events = []

        async def event_emitter(event):
            events.append(event)

        run_action(
            action,
            {
                "model": "gpt-test",
                "chat_id": "chat-1",
                "id": "msg-from-action-payload",
            },
            __id__="positive",
            __user__={"id": "user-1"},
            __event_emitter__=event_emitter,
        )

        self.assertEqual(scores[0]["trace_id"], "owui-chat-1-msg-from-action-payload")
        self.assertEqual(scores[0]["metadata"]["message_id"], "msg-from-action-payload")
        self.assertEqual(events[-1]["data"]["type"], "success")

    def test_action_buttons_have_readable_names_and_icons(self):
        module = load_action_module()

        for action in module.Action.actions:
            self.assertNotIn("_", action["name"])
            self.assertTrue(action["icon_url"].startswith("https://"))
            self.assertTrue(action["icon_url"].endswith(".svg"))

        actions_by_id = {action["id"]: action for action in module.Action.actions}
        self.assertTrue(actions_by_id["positive"]["icon_url"].endswith("/smile.svg"))
        self.assertTrue(actions_by_id["negative"]["icon_url"].endswith("/frown.svg"))

    def test_prompt_issue_collects_comment_and_scores_negative_feedback(self):
        module = load_action_module()
        action = module.Action()
        action.valves.langfuse_public_key = "pk-test"
        action.valves.langfuse_secret_key = "sk-test"
        scores = []
        capture_scores(action, scores)

        async def event_call(event):
            self.assertEqual(event["type"], "input")
            return "La reponse ignore la consigne."

        run_action(
            action,
            {"model": "gpt-test"},
            __id__="prompt_issue",
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-2"},
            __event_call__=event_call,
        )

        self.assertEqual(scores[0]["value"], 0.0)
        self.assertEqual(scores[0]["comment"], "La reponse ignore la consigne.")
        self.assertEqual(scores[1]["value"], "prompt_issue")
        self.assertEqual(scores[1]["comment"], "La reponse ignore la consigne.")

    def test_missing_chat_or_message_id_notifies_error_without_score(self):
        module = load_action_module()
        action = module.Action()
        action.valves.langfuse_public_key = "pk-test"
        action.valves.langfuse_secret_key = "sk-test"
        scores = []
        capture_scores(action, scores)
        events = []

        async def event_emitter(event):
            events.append(event)

        run_action(
            action,
            {},
            __id__="negative",
            __metadata__={"chat_id": "chat-1"},
            __event_emitter__=event_emitter,
        )

        self.assertEqual(scores, [])
        self.assertEqual(events[-1]["data"]["type"], "error")
        self.assertIn("chat_id", events[-1]["data"]["content"])

    def test_score_post_failure_notifies_error(self):
        module = load_action_module()
        action = module.Action()
        action.valves.langfuse_public_key = "pk-test"
        action.valves.langfuse_secret_key = "sk-test"

        async def failing_post(**kwargs):
            raise RuntimeError("Langfuse score creation failed (500): boom")

        action._post_score = failing_post
        events = []

        async def event_emitter(event):
            events.append(event)

        run_action(
            action,
            {"model": "gpt-test"},
            __id__="negative",
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
            __event_emitter__=event_emitter,
        )

        self.assertEqual(events[-1]["data"]["type"], "error")
        self.assertIn("Langfuse feedback failed", events[-1]["data"]["content"])


if __name__ == "__main__":
    unittest.main()
