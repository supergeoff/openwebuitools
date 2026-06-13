import importlib.util
import io
import os
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-prompts.py"
PROMPT_PATH = ROOT / "prompts" / "global.md"


def load_deploy_prompts_module():
    spec = importlib.util.spec_from_file_location("deploy_prompts", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployPromptsParsingTests(unittest.TestCase):
    def test_global_prompt_declares_langfuse_target_used_by_system_filter(self):
        module = load_deploy_prompts_module()

        definition = module.parse_prompt_file(PROMPT_PATH, label="production")

        self.assertEqual(definition.name, "global")
        self.assertEqual(definition.label, "production")
        self.assertEqual(definition.type, "text")
        self.assertIn("{{hindsight_bankid}}", definition.prompt)
        self.assertNotIn("---", definition.prompt)

    def test_prompt_name_comes_from_filename_and_label_from_config(self):
        module = load_deploy_prompts_module()

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "support.md"
            prompt_file.write_text("Support prompt body\n", encoding="utf-8")

            definition = module.parse_prompt_file(prompt_file, label="production")

        self.assertEqual(definition.name, "support")
        self.assertEqual(definition.label, "production")
        self.assertEqual(definition.type, "text")
        self.assertEqual(definition.prompt, "Support prompt body")

    def test_deploy_prompt_creates_text_prompt_with_production_label(self):
        module = load_deploy_prompts_module()
        calls = []

        class FakeLangfuse:
            def create_prompt(self, **kwargs):
                calls.append(kwargs)
                return types.SimpleNamespace(version=7, labels=["production", "latest"])

        definition = module.PromptDefinition(
            path=Path("prompts/global.md"),
            name="global",
            label="production",
            type="text",
            prompt="Hello {{hindsight_bankid}}",
        )

        with redirect_stdout(io.StringIO()):
            module.deploy_prompt(FakeLangfuse(), definition)

        self.assertEqual(
            calls,
            [
                {
                    "name": "global",
                    "prompt": "Hello {{hindsight_bankid}}",
                    "labels": ["production"],
                    "type": "text",
                }
            ],
        )

    def test_langfuse_deployment_config_requires_action_secrets(self):
        module = load_deploy_prompts_module()

        with patch.dict(os.environ, {}, clear=True):
            with redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    module.read_deployment_config()

        with patch.dict(
            os.environ,
            {
                "LANGFUSE_HOST": "https://langfuse.example.test",
                "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
                "LANGFUSE_SECRET_KEY": "sk-lf-test",
                "LANGFUSE_PROMPT_LABEL": "production",
            },
            clear=True,
        ):
            config = module.read_deployment_config()

        self.assertEqual(config.host, "https://langfuse.example.test")
        self.assertEqual(config.prompt_label, "production")


if __name__ == "__main__":
    unittest.main()
