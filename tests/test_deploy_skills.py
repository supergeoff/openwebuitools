import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / ".github" / "scripts" / "deploy-skills.py"


def load_deploy_skills_module():
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

    spec = importlib.util.spec_from_file_location("deploy_skills", SCRIPT_PATH)
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


class DeploySkillsTest(unittest.TestCase):
    def build_bundle(self, module, name):
        return module.SkillBundle(
            source_url=f"local://skills/{name}",
            target=module.GHTarget(
                owner="local",
                repo="skills",
                ref="main",
                path=name,
            ),
            skill_md=(
                "---\n"
                f"name: {name}\n"
                "description: Test skill\n"
                "---\n"
                "\n"
                "# Skill\n"
            ),
        )

    def test_skill_id_is_snake_case_and_display_name_is_title_case(self):
        module = load_deploy_skills_module()

        payload = module.build_payload(self.build_bundle(module, "my cool-tool"))

        self.assertFalse(hasattr(module, "DISPLAY_NAME_OVERRIDES"))
        self.assertEqual(payload.id, "my_cool_tool")
        self.assertEqual(payload.name, "My Cool Tool")

    def test_question_and_brainstorming_names_follow_generic_case_rule(self):
        module = load_deploy_skills_module()

        question = module.build_payload(self.build_bundle(module, "question"))
        brainstorming = module.build_payload(self.build_bundle(module, "brainstorming"))

        self.assertEqual(question.id, "question")
        self.assertEqual(question.name, "Question")
        self.assertEqual(brainstorming.id, "brainstorming")
        self.assertEqual(brainstorming.name, "Brainstorming")

    def test_web_search_local_skill_is_discovered_for_deployment(self):
        module = load_deploy_skills_module()

        bundles = module.discover_local_skills(str(ROOT / "skills"))
        payloads = [module.build_payload(bundle) for bundle in bundles]
        payloads = [payload for payload in payloads if payload is not None]
        web_search = next(payload for payload in payloads if payload.id == "web_search")

        self.assertEqual(web_search.name, "Web Search")
        self.assertIn("SearXNG", web_search.content)
        self.assertIn("crawl4ai", web_search.content)
        self.assertIn("deep & wide", web_search.content)


if __name__ == "__main__":
    unittest.main()
