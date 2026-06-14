import importlib.util
import asyncio
import inspect
import logging
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILTER_PATH = ROOT / "filters" / "system.py"


def load_filter_module():
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

    spec = importlib.util.spec_from_file_location("system_filter", FILTER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_inlet(filter_, body, **kwargs):
    result = filter_.inlet(body, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class SystemFilterTest(unittest.TestCase):
    def test_langfuse_prompt_receives_hindsight_bankid_from_user_valve_only(self):
        module = load_filter_module()
        filter_ = module.Filter()

        calls = []

        class Prompt:
            def compile(self, **kwargs):
                calls.append(kwargs)
                return "GLOBAL POLICY"

        class Client:
            def get_prompt(self, *args, **kwargs):
                return Prompt()

        filter_._client = Client()

        user = {
            "id": "user-123",
            "email": "geoff@example.com",
            "name": "Geoff User",
            "valves": {"hindsight_bankid": "geoff-bank"},
        }
        body = {"messages": [{"role": "user", "content": "Salut"}]}

        result = run_inlet(filter_, body, __user__=user)

        self.assertEqual(calls, [{"hindsight_bankid": "geoff-bank"}])
        content = result["messages"][0]["content"]
        self.assertIn("GLOBAL POLICY", content)
        self.assertNotIn("Geoff User", content)
        self.assertNotIn("geoff@example.com", content)
        self.assertNotIn("user-123", content)

    def test_hindsight_bankid_supports_user_valves_object(self):
        module = load_filter_module()
        filter_ = module.Filter()

        class UserValves:
            hindsight_bankid = "alice-bank"

        class Prompt:
            def compile(self, **kwargs):
                return f"bankid={kwargs['hindsight_bankid']}"

        class Client:
            def get_prompt(self, *args, **kwargs):
                return Prompt()

        filter_._client = Client()

        body = {"messages": [{"role": "user", "content": "Hello"}]}
        result = run_inlet(filter_, body, __user__={"valves": UserValves()})

        self.assertEqual(result["messages"][0]["content"], "bankid=alice-bank")

    def test_missing_user_bankid_compiles_empty_prompt_variable(self):
        module = load_filter_module()
        filter_ = module.Filter()

        calls = []

        class Prompt:
            def compile(self, **kwargs):
                calls.append(kwargs)
                return "GLOBAL POLICY"

        class Client:
            def get_prompt(self, *args, **kwargs):
                return Prompt()

        filter_._client = Client()

        body = {"messages": [{"role": "user", "content": "Hello"}]}
        result = run_inlet(
            filter_,
            body,
            __user__={"id": "user-123", "email": "geoff@example.com", "name": "Geoff"},
        )

        self.assertEqual(calls, [{"hindsight_bankid": ""}])
        content = result["messages"][0]["content"]
        self.assertIn("GLOBAL POLICY", content)
        self.assertNotIn("Geoff", content)
        self.assertNotIn("geoff@example.com", content)
        self.assertNotIn("user-123", content)

    def test_filter_has_only_user_bankid_for_hindsight(self):
        module = load_filter_module()
        filter_ = module.Filter()

        self.assertFalse(hasattr(filter_, "_fetch_hindsight_memory"))
        self.assertFalse(hasattr(filter_, "_build_hindsight_mcp_instruction"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_host"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_path"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_auth_header"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_mcp_enabled"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_injection_prefix"))
        self.assertTrue(hasattr(filter_.user_valves, "hindsight_bankid"))

    def test_existing_system_prompt_is_preserved_after_injections(self):
        module = load_filter_module()
        filter_ = module.Filter()

        body = {
            "messages": [
                {"role": "system", "content": "Existing model policy."},
                {"role": "user", "content": "Hello"},
            ]
        }

        class Prompt:
            def compile(self, **kwargs):
                return f"GLOBAL POLICY {kwargs['hindsight_bankid']}"

        class Client:
            def get_prompt(self, *args, **kwargs):
                return Prompt()

        filter_._client = Client()
        result = run_inlet(
            filter_,
            body,
            __user__={"name": "Alice", "valves": {"hindsight_bankid": "Alice"}},
        )

        self.assertEqual(result["messages"][0]["role"], "system")
        content = result["messages"][0]["content"]
        self.assertTrue(content.startswith("GLOBAL POLICY Alice"))
        self.assertTrue(content.endswith("Existing model policy."))

    def test_forced_tool_ids_are_added_without_duplicates(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_tool_ids = "alpha, beta, alpha"

        body = {
            "tool_ids": ["existing", "alpha"],
            "messages": [{"role": "user", "content": "Hello"}],
        }

        async def no_unresolved(tool_ids, __request__=None):
            return []

        filter_._get_unresolved_forced_tool_ids = no_unresolved

        result = run_inlet(filter_, body)

        self.assertEqual(result["tool_ids"], ["existing", "alpha", "beta"])

    def test_unresolved_forced_tool_ids_are_logged_once(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_tool_ids = "missing, available"

        async def fake_unresolved(tool_ids, __request__=None):
            return ["missing"]

        filter_._get_unresolved_forced_tool_ids = fake_unresolved

        logger = logging.getLogger("global_policy_filter")
        with self.assertLogs(logger, level="WARNING") as logs:
            run_inlet(
                filter_, {"messages": [{"role": "user", "content": "Hello"}]}
            )
            run_inlet(
                filter_, {"messages": [{"role": "user", "content": "Hello"}]}
            )

        self.assertEqual(len(logs.output), 1)
        self.assertIn("missing", logs.output[0])

    def test_unresolved_forced_mcp_server_ids_are_logged_once(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_tool_ids = "server:mcp:missing, server:mcp:available"

        request = types.SimpleNamespace(
            app=types.SimpleNamespace(
                state=types.SimpleNamespace(
                    config=types.SimpleNamespace(
                        TOOL_SERVER_CONNECTIONS=[
                            {"type": "mcp", "info": {"id": "available"}}
                        ]
                    )
                )
            )
        )

        logger = logging.getLogger("global_policy_filter")
        with self.assertLogs(logger, level="WARNING") as logs:
            run_inlet(
                filter_,
                {"messages": [{"role": "user", "content": "Hello"}]},
                __request__=request,
            )
            run_inlet(
                filter_,
                {"messages": [{"role": "user", "content": "Hello"}]},
                __request__=request,
            )

        self.assertEqual(len(logs.output), 1)
        self.assertIn("server:mcp:missing", logs.output[0])
        self.assertNotIn("server:mcp:available", logs.output[0])

    def test_forced_skill_ids_are_added_without_duplicates(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_skill_ids = "skill-a, skill-b, skill-a"

        body = {
            "skill_ids": ["existing", "skill-a"],
            "messages": [{"role": "user", "content": "Hello"}],
        }

        async def no_unresolved(skill_ids, __user__=None):
            return []

        filter_._get_unresolved_forced_skill_ids = no_unresolved

        result = run_inlet(filter_, body)

        self.assertEqual(result["skill_ids"], ["existing", "skill-a", "skill-b"])

    def test_unresolved_forced_skill_ids_are_logged_once(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_skill_ids = "missing, available"

        async def fake_unresolved(skill_ids, __user__=None):
            return ["missing"]

        filter_._get_unresolved_forced_skill_ids = fake_unresolved

        logger = logging.getLogger("global_policy_filter")
        with self.assertLogs(logger, level="WARNING") as logs:
            run_inlet(
                filter_, {"messages": [{"role": "user", "content": "Hello"}]}
            )
            run_inlet(
                filter_, {"messages": [{"role": "user", "content": "Hello"}]}
            )

        self.assertEqual(len(logs.output), 1)
        self.assertIn("missing", logs.output[0])

    def test_inactive_forced_skill_ids_are_unresolved(self):
        module = load_filter_module()
        filter_ = module.Filter()

        class Skill:
            def __init__(self, id, is_active=True):
                self.id = id
                self.is_active = is_active

        class Skills:
            @staticmethod
            async def get_skills_by_user_id(user_id, permission):
                return [Skill("active"), Skill("inactive", is_active=False)]

            @staticmethod
            async def get_skill_by_id(skill_id):
                return {
                    "active": Skill("active"),
                    "inactive": Skill("inactive", is_active=False),
                }.get(skill_id)

        open_webui = types.ModuleType("open_webui")
        models = types.ModuleType("open_webui.models")
        skills_module = types.ModuleType("open_webui.models.skills")
        skills_module.Skills = Skills

        original_modules = {
            name: sys.modules.get(name)
            for name in [
                "open_webui",
                "open_webui.models",
                "open_webui.models.skills",
            ]
        }
        sys.modules["open_webui"] = open_webui
        sys.modules["open_webui.models"] = models
        sys.modules["open_webui.models.skills"] = skills_module
        try:
            unresolved = asyncio.run(
                filter_._get_unresolved_forced_skill_ids(
                    ["active", "inactive", "missing"],
                    __user__={"id": "user-1"},
                )
            )
        finally:
            for name, original in original_modules.items():
                if original is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = original

        self.assertEqual(unresolved, ["inactive", "missing"])


if __name__ == "__main__":
    unittest.main()
