import importlib.util
import io
import os
import re
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-prompts.py"
PROMPT_DIR = ROOT / "prompts"
REQUIRED_PROMPTS = [
    "memory",
    "output_style",
    "skills",
    "task_management",
    "tools",
    "evaluator_owui_judge",
]
SYSTEM_PROMPT_MODULES = ["output_style", "tools", "memory", "skills", "task_management"]


def load_deploy_prompts_module():
    spec = importlib.util.spec_from_file_location("deploy_prompts", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployPromptsParsingTests(unittest.TestCase):
    def test_required_split_prompt_modules_exist_without_global_legacy_prompt(self):
        module = load_deploy_prompts_module()

        self.assertFalse((PROMPT_DIR / "global.md").exists())

        definitions = [
            module.parse_prompt_file(PROMPT_DIR / f"{name}.md", label="production")
            for name in REQUIRED_PROMPTS
        ]

        self.assertEqual([definition.name for definition in definitions], REQUIRED_PROMPTS)
        for definition in definitions:
            self.assertEqual(definition.label, "production")
            self.assertEqual(definition.type, "text")
            self.assertGreater(len(definition.prompt), 40)
            self.assertNotIn("---", definition.prompt)

    def test_split_prompt_content_keeps_known_policy_anchors(self):
        module = load_deploy_prompts_module()

        def load(name):
            return module.parse_prompt_file(PROMPT_DIR / f"{name}.md", label="production")

        output_style = load("output_style")
        tools = load("tools")
        memory = load("memory")
        skills = load("skills")
        task_management = load("task_management")

        self.assertTrue(output_style.prompt.startswith("# Langue et style"))
        self.assertIn("JAMAIS DE STYLE TÉLÉGRAPHIQUE", output_style.prompt)
        self.assertTrue(tools.prompt.startswith("# Outils et sources"))
        self.assertIn("search_tools", tools.prompt)
        self.assertIn("call_tool_write", tools.prompt)
        self.assertTrue(memory.prompt.startswith("# Mémoire Hindsight (obligatoire)"))
        self.assertIn("list_mental_models", memory.prompt)
        self.assertIn('tags_match "any_strict"', memory.prompt)
        self.assertIn('list_tags avec q "s:*"', memory.prompt)
        self.assertIn("aucun identifiant de banque", memory.prompt)
        self.assertTrue(skills.prompt.startswith("# Skills et recherche web"))
        self.assertIn("skill web-search", skills.prompt)
        self.assertIn("create_tasks", task_management.prompt)
        self.assertIn("update_task", task_management.prompt)

    def test_system_prompt_modules_have_no_template_variables(self):
        # The system filter compiles modules without variables, so a literal
        # mustache tag would reach the model unresolved.
        module = load_deploy_prompts_module()

        for name in SYSTEM_PROMPT_MODULES:
            definition = module.parse_prompt_file(
                PROMPT_DIR / f"{name}.md", label="production"
            )
            self.assertNotIn("{{", definition.prompt, name)

    def test_system_prompt_modules_stay_user_neutral(self):
        # The repo serves every Open WebUI user: the system prompt must not
        # speak in one user's voice or name one user's domains or tools.
        module = load_deploy_prompts_module()
        first_person = re.compile(r"\b(je|j'|moi|me|mes|mon|ma)\b", re.IGNORECASE)
        personal_terms = ["septeo", "stack-perso", "bitwarden", "geoff"]

        for name in SYSTEM_PROMPT_MODULES:
            definition = module.parse_prompt_file(
                PROMPT_DIR / f"{name}.md", label="production"
            )
            self.assertIsNone(first_person.search(definition.prompt), name)
            for term in personal_terms:
                self.assertNotIn(term, definition.prompt.lower(), name)

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
            path=Path("prompts/core.md"),
            name="core",
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
                    "name": "core",
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
