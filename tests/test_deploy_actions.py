import importlib.util
import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-actions.py"


def load_deploy_actions_module():
    original_requests = sys.modules.get("requests")

    requests = types.ModuleType("requests")
    requests.get = lambda *args, **kwargs: None
    requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests

    spec = importlib.util.spec_from_file_location("deploy_actions", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if original_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = original_requests

    return module


class DeployActionsTest(unittest.TestCase):
    def test_action_is_created_then_toggled_active_and_global(self):
        module = load_deploy_actions_module()
        posts = []

        class Response:
            status_code = 201
            text = ""

            def json(self):
                return {"id": "langfuse_feedback", "is_active": False, "is_global": False}

        def fake_post(url, headers=None, json=None, timeout=None):
            posts.append(
                {
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            return Response()

        module.requests.post = fake_post

        with tempfile.TemporaryDirectory() as tmpdir:
            action_file = Path(tmpdir) / "langfuse-feedback.py"
            action_file.write_text(
                '"""\n'
                "title: Langfuse Feedback\n"
                "description: Send feedback to Langfuse\n"
                '"""\n'
                "\n"
                "class Action:\n"
                "    pass\n",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                self.assertTrue(
                    module.deploy_action(
                        "https://openwebui.example.test",
                        "test-key",
                        action_file,
                        installed_functions=[],
                    )
                )

        self.assertEqual(posts[0]["url"], "https://openwebui.example.test/api/v1/functions/create")
        self.assertEqual(posts[0]["json"]["id"], "langfuse_feedback")
        self.assertEqual(posts[0]["json"]["name"], "Langfuse_Feedback")
        self.assertIn("class Action", posts[0]["json"]["content"])
        self.assertEqual(
            [post["url"] for post in posts[1:]],
            [
                "https://openwebui.example.test/api/v1/functions/id/langfuse_feedback/toggle",
                "https://openwebui.example.test/api/v1/functions/id/langfuse_feedback/toggle/global",
            ],
        )

    def test_existing_active_global_action_is_updated_without_toggles(self):
        module = load_deploy_actions_module()
        posts = []

        class Response:
            status_code = 200
            text = ""

            def json(self):
                return {"id": "langfuse_feedback", "is_active": True, "is_global": True}

        def fake_post(url, headers=None, json=None, timeout=None):
            posts.append({"url": url, "json": json})
            return Response()

        module.requests.post = fake_post

        with tempfile.TemporaryDirectory() as tmpdir:
            action_file = Path(tmpdir) / "langfuse_feedback.py"
            action_file.write_text("class Action:\n    pass\n", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                self.assertTrue(
                    module.deploy_action(
                        "https://openwebui.example.test",
                        "test-key",
                        action_file,
                        installed_functions=[
                            {
                                "id": "langfuse_feedback",
                                "is_active": True,
                                "is_global": True,
                            }
                        ],
                    )
                )

        self.assertEqual(
            [post["url"] for post in posts],
            [
                "https://openwebui.example.test/api/v1/functions/id/langfuse_feedback/update",
            ],
        )


if __name__ == "__main__":
    unittest.main()
