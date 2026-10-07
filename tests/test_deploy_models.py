import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-models.py"
GENERATED_MODULES = ("style", "broker", "memory", "skills", "conduct")


def real_yaml():
    """Return PyYAML even when another test left a stub in sys.modules, or None."""
    stub = sys.modules.pop("yaml", None)
    try:
        return importlib.import_module("yaml")
    except ImportError:
        return None
    finally:
        if stub is not None:
            sys.modules["yaml"] = stub


YAML = real_yaml()


def load_deploy_models_module():
    """Import deploy-models.py with a stubbed requests and the real yaml when available."""
    requests = types.ModuleType("requests")
    requests.get = lambda *args, **kwargs: None
    requests.post = lambda *args, **kwargs: None
    saved = {name: sys.modules.get(name) for name in ("requests", "yaml")}
    sys.modules["requests"] = requests
    sys.modules["yaml"] = YAML or types.ModuleType("yaml")
    try:
        spec = importlib.util.spec_from_file_location("deploy_models", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, value in saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    return module


class AssemblePromptTests(unittest.TestCase):
    def setUp(self):
        self.module = load_deploy_models_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.prompts = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_modules_are_joined_in_order_without_their_generated_header(self):
        (self.prompts / "one.md").write_text("<!-- Généré par sync-clients.py. -->\n\n# One\n\nFirst.\n")
        (self.prompts / "two.md").write_text("# Two\n\nSecond.\n")

        prompt = self.module.assemble_prompt(["two", "one"], self.prompts)

        self.assertEqual(prompt, "# Two\n\nSecond.\n\n# One\n\nFirst.")

    def test_a_missing_module_is_an_error(self):
        with self.assertRaises(ValueError):
            self.module.assemble_prompt(["absent"], self.prompts)

    def test_an_empty_module_is_an_error(self):
        (self.prompts / "empty.md").write_text("<!-- header only -->\n")

        with self.assertRaises(ValueError):
            self.module.assemble_prompt(["empty"], self.prompts)


class ModelPayloadTests(unittest.TestCase):
    def setUp(self):
        self.module = load_deploy_models_module()
        self.config = {
            "id": "auto",
            "prompt_modules": ["style"],
            "meta": {"toolIds": ["server:mcp:tools"], "skillIds": ["coder"]},
        }

    def test_update_sets_prompt_tools_and_skills_and_keeps_the_rest_of_the_live_config(self):
        existing = {
            "id": "auto",
            "user_id": "u1",
            "base_model_id": None,
            "name": "auto",
            "params": {"function_calling": "native"},
            "meta": {
                "description": "Routeur",
                "terminalId": "terminal",
                "toolIds": ["server:mcp:searxng"],
                "skillIds": ["question"],
            },
            "access_grants": [
                {
                    "id": "g1",
                    "resource_type": "model",
                    "resource_id": "auto",
                    "principal_type": "user",
                    "principal_id": "*",
                    "permission": "read",
                }
            ],
            "is_active": True,
            "updated_at": 1,
        }

        payload = self.module.build_update(existing, self.config, "PROMPT")

        self.assertEqual(payload["params"], {"function_calling": "native", "system": "PROMPT"})
        self.assertEqual(payload["meta"]["toolIds"], ["server:mcp:tools"])
        self.assertEqual(payload["meta"]["skillIds"], ["coder"])
        self.assertEqual(payload["meta"]["terminalId"], "terminal")
        self.assertEqual(payload["meta"]["description"], "Routeur")
        self.assertEqual(
            payload["access_grants"], [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
        )
        self.assertNotIn("user_id", payload)
        self.assertEqual(existing["meta"]["toolIds"], ["server:mcp:searxng"])

    def test_a_new_model_is_created_readable_by_every_user(self):
        payload = self.module.build_create(self.config, "PROMPT")

        self.assertEqual(payload["id"], "auto")
        self.assertIsNone(payload["base_model_id"])
        self.assertEqual(payload["params"], {"system": "PROMPT"})
        self.assertEqual(
            payload["access_grants"], [{"principal_type": "user", "principal_id": "*", "permission": "read"}]
        )


@unittest.skipIf(YAML is None, "PyYAML is required to read models/auto.yaml")
class RepositoryConfigTests(unittest.TestCase):
    def setUp(self):
        self.module = load_deploy_models_module()

    def test_the_auto_model_prompt_assembles_from_the_repository_modules(self):
        config = self.module.load_config(ROOT / "models" / "auto.yaml")

        prompt = self.module.assemble_prompt(config["prompt_modules"])

        self.assertEqual(config["id"], "auto")
        self.assertIn("# Outils et broker MCP", prompt)
        self.assertIn("# Open WebUI", prompt)
        self.assertNotIn("<!--", prompt)

    def test_generated_modules_point_back_to_the_agents_repo(self):
        for name in GENERATED_MODULES:
            with self.subTest(module=name):
                text = (ROOT / "prompts" / f"{name}.md").read_text(encoding="utf-8")

                self.assertTrue(text.startswith("<!-- Généré par scripts/sync-clients.py"))

    def test_the_system_prompt_names_no_single_user(self):
        config = self.module.load_config(ROOT / "models" / "auto.yaml")

        prompt = self.module.assemble_prompt(config["prompt_modules"])

        for term in ("d:septeo", "d:stack-perso", "Bitwarden", "Geoff", "mes serveurs"):
            with self.subTest(term=term):
                self.assertNotIn(term, prompt)


if __name__ == "__main__":
    unittest.main()
