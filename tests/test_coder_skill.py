import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "skills" / "coder" / "SKILL.md"
CODING_PROMPT_PATH = ROOT / "prompts" / "coding.md"
DEPLOY_SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-skills.py"


# Exact Coder MCP tool names the skill is contracted to document. These are the
# verbatim names exposed by github.com/coder/coder (codersdk/toolsdk); if upstream
# renames a tool, this test should fail so the skill stays accurate.
CORE_CODER_TOOLS = [
    "coder_workspace_bash",
    "coder_workspace_ls",
    "coder_workspace_read_file",
    "coder_workspace_write_file",
    "coder_workspace_edit_files",
    "coder_workspace_port_forward",
    "coder_report_task",
    "coder_get_workspace",
    "coder_list_workspaces",
]


def load_deploy_skills_module():
    """Import .github/scripts/deploy-skills.py with stubbed requests/yaml.

    Mirrors tests/test_deploy_skills.py so this file stays self-contained.
    """
    original_requests = sys.modules.get("requests")
    original_yaml = sys.modules.get("yaml")

    requests = types.ModuleType("requests")
    requests.Session = object
    requests.HTTPError = Exception
    requests.RequestException = Exception

    yaml = types.ModuleType("yaml")
    yaml.YAMLError = Exception

    def safe_load(value):
        result = {}
        for line in value.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            result[key.strip()] = raw.strip().strip('"')
        return result

    yaml.safe_load = safe_load

    spec = importlib.util.spec_from_file_location("deploy_skills", DEPLOY_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.modules["requests"] = requests
    sys.modules["yaml"] = yaml
    try:
        spec.loader.exec_module(module)
    finally:
        if original_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = original_requests

        if original_yaml is None:
            sys.modules.pop("yaml", None)
        else:
            sys.modules["yaml"] = original_yaml

    return module


class CoderReactSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill_text = SKILL_PATH.read_text(encoding="utf-8")
        cls.coding_prompt = CODING_PROMPT_PATH.read_text(encoding="utf-8")

    def test_skill_names_every_core_coder_mcp_tool(self):
        for tool in CORE_CODER_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, self.skill_text)

    def test_skill_documents_the_react_loop(self):
        expected_snippets = [
            "ReAct",
            "Reason + Act",
            "Thought -> Action -> Observation",
            "One action per step",
            "single source of truth",
        ]
        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.skill_text)

    def test_skill_enforces_artifact_retrieval(self):
        # read back -> verify -> list, the closed-loop contract
        expected_snippets = [
            "Artifact retrieval",
            "Read back",
            "Verify",
            "List",
            "Artifacts",
        ]
        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.skill_text)

    def test_skill_disambiguates_from_the_javascript_framework(self):
        self.assertIn("not the JavaScript framework", self.skill_text)

    def test_finished_states_are_gated_consistently(self):
        # Both `complete` and `idle` are terminal "done" states for
        # coder_report_task; the artifact gate must cover both, and SKILL.md and
        # coding.md must agree on the terminal-state set.
        self.assertIn("`complete` or `idle`", self.skill_text)
        self.assertIn("`complete` or `idle`", self.coding_prompt)

    def test_coding_prompt_enforces_coder_react_loop(self):
        expected_snippets = [
            "Coder Workspace ReAct Loop",
            "<HARD-GATE>",
            "coder_workspace_bash",
            "coder_report_task",
            "`coder` skill",
        ]
        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.coding_prompt)


class CoderReactSkillDeploymentTests(unittest.TestCase):
    def test_skill_is_discovered_and_named_for_deployment(self):
        module = load_deploy_skills_module()

        bundles = module.discover_local_skills(str(ROOT / "skills"))
        payloads = [module.build_payload(bundle) for bundle in bundles]
        payloads = [payload for payload in payloads if payload is not None]
        coder = next(
            (payload for payload in payloads if payload.id == "coder"), None
        )

        self.assertIsNotNone(coder, "coder skill was not discovered")
        self.assertEqual(coder.name, "Coder")
        for tool in CORE_CODER_TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, coder.content)


if __name__ == "__main__":
    unittest.main()
