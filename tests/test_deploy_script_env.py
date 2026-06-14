import importlib.util
import io
import os
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPTS = sorted((ROOT / ".github" / "scripts").glob("deploy-*.py"))
OPENWEBUI_SCRIPTS = [
    ROOT / ".github" / "scripts" / "deploy-filters.py",
    ROOT / ".github" / "scripts" / "deploy-tools.py",
    ROOT / ".github" / "scripts" / "deploy-pipes.py",
    ROOT / ".github" / "scripts" / "deploy-models.py",
]


def load_script(path: Path):
    if "requests" not in sys.modules:
        requests = types.ModuleType("requests")
        requests.get = lambda *args, **kwargs: None
        requests.post = lambda *args, **kwargs: None
        sys.modules["requests"] = requests

    if "yaml" not in sys.modules:
        yaml = types.ModuleType("yaml")
        yaml.safe_load = lambda value: {}
        sys.modules["yaml"] = yaml

    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeployScriptEnvTests(unittest.TestCase):
    def test_openwebui_scripts_require_url_from_environment(self):
        for script_path in OPENWEBUI_SCRIPTS:
            with self.subTest(script=script_path.name):
                module = load_script(script_path)

                with patch.dict(os.environ, {}, clear=True):
                    with redirect_stdout(io.StringIO()):
                        with self.assertRaises(SystemExit):
                            module.require_env("OPENWEBUI_URL")

                with patch.dict(
                    os.environ,
                    {"OPENWEBUI_URL": "https://openwebui.example.test/"},
                    clear=True,
                ):
                    self.assertEqual(
                        module.require_env("OPENWEBUI_URL"),
                        "https://openwebui.example.test/",
                    )

    def test_deployment_scripts_do_not_contain_environment_defaults(self):
        for script_path in DEPLOY_SCRIPTS:
            with self.subTest(script=script_path.name):
                source = script_path.read_text(encoding="utf-8")

                self.assertNotRegex(source, r"os\.getenv\([^\n]+,")
                self.assertNotIn("DEFAULT_LANGFUSE_HOST", source)
                self.assertNotIn("DEFAULT_LABEL", source)

    def test_deploy_skills_workflow_runs_when_deploy_script_changes(self):
        workflow = ROOT / ".github" / "workflows" / "deploy-skills.yml"
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("'.github/scripts/deploy-skills.py'", source)
        self.assertIn("'.github/workflows/deploy-skills.yml'", source)

    def test_deploy_tools_workflow_runs_when_deploy_script_changes(self):
        workflow = ROOT / ".github" / "workflows" / "deploy-tools.yml"
        source = workflow.read_text(encoding="utf-8")

        self.assertIn("'.github/scripts/deploy-tools.py'", source)
        self.assertIn("'.github/workflows/deploy-tools.yml'", source)
