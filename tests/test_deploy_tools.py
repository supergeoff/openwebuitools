import importlib.util
import io
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-tools.py"


def load_deploy_tools_module():
    original_requests = sys.modules.get("requests")

    requests = types.ModuleType("requests")
    requests.get = lambda *args, **kwargs: None
    requests.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests

    spec = importlib.util.spec_from_file_location("deploy_tools", SCRIPT_PATH)
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


class DeployToolsTest(unittest.TestCase):
    def test_tool_id_is_snake_case_and_display_name_is_pascal_snake_case(self):
        module = load_deploy_tools_module()
        posts = []

        class Response:
            status_code = 201
            text = ""

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
            tool_file = Path(tmpdir) / "my-cool_tool.py"
            tool_file.write_text(
                '"""\n'
                "title: Custom Friendly Name\n"
                "description: Test tool\n"
                '"""\n'
                "\n"
                "class Tools:\n"
                "    pass\n",
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                self.assertTrue(
                    module.deploy_tool(
                        "https://openwebui.example.test",
                        "test-key",
                        tool_file,
                        installed_tools=[],
                    )
                )

        self.assertEqual(posts[0]["json"]["id"], "my_cool_tool")
        self.assertEqual(posts[0]["json"]["name"], "My_Cool_Tool")


if __name__ == "__main__":
    unittest.main()
