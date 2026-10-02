import asyncio
import sys
import types
import unittest

from tests.test_system_filter import load_filter_module, run_inlet


class SystemFilterPassthroughTest(unittest.TestCase):
    def test_passthrough_model_skips_injection_and_strips_owui_tooling(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enable_tracing = False
        filter_.valves.forced_tool_ids = "server:mcp:hindsight,question_wizard"
        filter_.valves.forced_skill_ids = "brainstorming"

        async def fail_policy(__user__):
            raise AssertionError("prompt must not be fetched for passthrough models")

        filter_._fetch_policy = fail_policy

        body = {
            "model": "cptr/supergeoff",
            "tool_ids": ["server:mcp:github"],
            "skill_ids": ["coder"],
            "terminal_id": "open-terminal",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        result = run_inlet(filter_, body)

        self.assertNotIn("tool_ids", result)
        self.assertNotIn("skill_ids", result)
        self.assertNotIn("terminal_id", result)
        self.assertEqual(result["messages"], [{"role": "user", "content": "Hello"}])

    def test_passthrough_matches_workspace_model_built_on_gateway_model(self):
        module = load_filter_module()
        filter_ = module.Filter()

        self.assertTrue(
            filter_._is_passthrough_model(
                {"model": "my-coder"},
                {"id": "my-coder", "info": {"base_model_id": "cptr/supergeoff"}},
            )
        )
        self.assertFalse(filter_._is_passthrough_model({"model": "auto"}, None))

        filter_.valves.passthrough_model_prefixes = ""
        self.assertFalse(filter_._is_passthrough_model({"model": "cptr/x"}, None))

    def test_passthrough_model_is_still_traced(self):
        module = load_filter_module()
        filter_ = module.Filter()
        captured = []
        filter_._spawn_ingestion = captured.extend

        run_inlet(
            filter_,
            {"model": "cptr/supergeoff", "messages": [{"role": "user", "content": "Hi"}]},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
        )

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["body"]["id"], "owui-chat-1-msg-1")

    def test_forced_skill_validation_uses_get_skills_on_recent_open_webui(self):
        module = load_filter_module()
        filter_ = module.Filter()
        calls = []

        class Skill:
            def __init__(self, id, is_active=True):
                self.id = id
                self.is_active = is_active

        class Skills:
            @staticmethod
            async def get_skills(user_id=None, ids=None):
                calls.append((user_id, ids))
                return [Skill("active")]

            @staticmethod
            async def get_skill_by_id(skill_id):
                return Skill("active") if skill_id == "active" else None

        open_webui = types.ModuleType("open_webui")
        models = types.ModuleType("open_webui.models")
        skills_module = types.ModuleType("open_webui.models.skills")
        skills_module.Skills = Skills

        names = ["open_webui", "open_webui.models", "open_webui.models.skills"]
        original_modules = {name: sys.modules.get(name) for name in names}
        sys.modules["open_webui"] = open_webui
        sys.modules["open_webui.models"] = models
        sys.modules["open_webui.models.skills"] = skills_module
        try:
            unresolved = asyncio.run(
                filter_._get_unresolved_forced_skill_ids(
                    ["active", "missing"], __user__={"id": "user-1"}
                )
            )
        finally:
            for name, original in original_modules.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original

        self.assertEqual(calls, [("user-1", ["active", "missing"])])
        self.assertEqual(unresolved, ["missing"])


if __name__ == "__main__":
    unittest.main()
