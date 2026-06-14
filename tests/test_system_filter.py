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


def run_outlet(filter_, body, **kwargs):
    result = filter_.outlet(body, **kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


class SystemFilterTest(unittest.TestCase):
    def test_memory_prompt_receives_hindsight_bankid_from_user_valve_only(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("memory",)
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
        module.PROMPT_MODULES = ("memory",)
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

        self.assertIn("bankid=alice-bank", result["messages"][0]["content"])
        self.assertIn("# Prompt Module: memory", result["messages"][0]["content"])

    def test_missing_user_bankid_compiles_empty_prompt_variable(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("memory",)
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
        self.assertFalse(hasattr(filter_.valves, "prompt_names"))
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
                return "GLOBAL POLICY"

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
        self.assertTrue(content.startswith("# Prompt Module: core"))
        self.assertIn("GLOBAL POLICY", content)
        self.assertTrue(content.endswith("Existing model policy."))

    def test_forced_tool_ids_are_added_without_duplicates(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enabled = False
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
        filter_.valves.enabled = False
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
        filter_.valves.enabled = False
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
        filter_.valves.enabled = False
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
        filter_.valves.enabled = False
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

    def test_builtin_prompt_modules_include_task_management(self):
        module = load_filter_module()
        filter_ = module.Filter()

        self.assertEqual(
            filter_._prompt_module_names(),
            [
                "core",
                "task_management",
                "memory",
                "tools",
                "research",
                "coding",
                "output_style",
            ],
        )

    def test_split_prompts_are_fetched_in_order_and_only_memory_receives_bankid(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("core", "task_management", "memory", "tools")
        filter_ = module.Filter()
        calls = []

        class Prompt:
            compile_calls = []

            def __init__(self, name):
                self.name = name

            def compile(self, **kwargs):
                self.compile_calls.append((self.name, kwargs))
                return f"{self.name}:{kwargs.get('hindsight_bankid', 'NO_BANKID')}"

        class Client:
            def get_prompt(self, name, **kwargs):
                calls.append((name, kwargs))
                return Prompt(name)

        filter_._client = Client()

        result = run_inlet(
            filter_,
            {"messages": [{"role": "user", "content": "Hello"}]},
            __user__={"valves": {"hindsight_bankid": "bank-1"}},
        )

        self.assertEqual(
            [name for name, _ in calls],
            ["core", "task_management", "memory", "tools"],
        )
        self.assertEqual(
            [kwargs["label"] for _, kwargs in calls],
            ["production", "production", "production", "production"],
        )
        self.assertEqual(Prompt.compile_calls, [
            ("core", {}),
            ("task_management", {}),
            ("memory", {"hindsight_bankid": "bank-1"}),
            ("tools", {}),
        ])
        content = result["messages"][0]["content"]
        self.assertLess(
            content.index("# Prompt Module: core"),
            content.index("# Prompt Module: task_management"),
        )
        self.assertLess(
            content.index("# Prompt Module: task_management"),
            content.index("# Prompt Module: memory"),
        )
        self.assertLess(content.index("# Prompt Module: memory"), content.index("# Prompt Module: tools"))
        self.assertIn("core:NO_BANKID", content)
        self.assertIn("task_management:NO_BANKID", content)
        self.assertIn("memory:bank-1", content)
        self.assertIn("tools:NO_BANKID", content)

    def test_missing_langfuse_keys_hard_fail_when_prompt_enabled(self):
        module = load_filter_module()
        filter_ = module.Filter()

        with self.assertRaisesRegex(RuntimeError, "Langfuse public and secret keys"):
            run_inlet(filter_, {"messages": [{"role": "user", "content": "Hello"}]})

    def test_langfuse_prompt_fetch_failure_hard_fails_with_module_name(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("core",)
        filter_ = module.Filter()

        class Client:
            def get_prompt(self, name, **kwargs):
                raise ValueError("not found")

        filter_._client = Client()

        with self.assertRaisesRegex(RuntimeError, "core.*production.*not found"):
            run_inlet(filter_, {"messages": [{"role": "user", "content": "Hello"}]})

    def test_empty_compiled_prompt_hard_fails_with_module_name(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("memory",)
        filter_ = module.Filter()

        class Prompt:
            def compile(self, **kwargs):
                return "   "

        class Client:
            def get_prompt(self, name, **kwargs):
                return Prompt()

        filter_._client = Client()

        with self.assertRaisesRegex(RuntimeError, "memory.*empty"):
            run_inlet(filter_, {"messages": [{"role": "user", "content": "Hello"}]})

    def test_trace_id_is_deterministic_for_chat_and_message(self):
        module = load_filter_module()
        filter_ = module.Filter()

        class Langfuse:
            @staticmethod
            def create_trace_id(*, seed=None):
                return f"trace::{seed}"

        langfuse_module = types.ModuleType("langfuse")
        langfuse_module.Langfuse = Langfuse
        original = sys.modules.get("langfuse")
        sys.modules["langfuse"] = langfuse_module
        try:
            self.assertEqual(
                filter_._build_trace_id("chat-1", "message-2"),
                "trace::owui:chat-1:message-2",
            )
        finally:
            if original is None:
                sys.modules.pop("langfuse", None)
            else:
                sys.modules["langfuse"] = original

    def test_outlet_records_langfuse_trace_with_prompt_metadata(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.forced_tool_ids = "server:mcp:memory"
        filter_.valves.forced_skill_ids = "brainstorming"
        started = []

        class Observation:
            def end(self):
                started[-1]["ended"] = True

        class Client:
            def start_observation(self, **kwargs):
                started.append(kwargs)
                return Observation()

            def _create_trace_tags_via_ingestion(self, **kwargs):
                started.append({"trace_tags": kwargs})

            def flush(self):
                started.append({"flushed": True})

        filter_._client = Client()
        filter_._build_trace_id = lambda chat_id, message_id: f"trace:{chat_id}:{message_id}"

        run_outlet(
            filter_,
            {
                "model": "gpt-test",
                "messages": [
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": "Answer"},
                ],
            },
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
        )

        trace = started[0]
        self.assertEqual(trace["trace_context"], {"trace_id": "trace:chat-1:msg-1"})
        self.assertEqual(trace["name"], "owui-chat-response")
        self.assertEqual(trace["input"], {"last_user_message": "Question"})
        self.assertEqual(trace["output"], {"assistant_message": "Answer"})
        self.assertNotIn("prompt_modules", trace["metadata"])
        self.assertEqual(trace["metadata"]["forced_tool_ids"], "server:mcp:memory")
        self.assertEqual(trace["metadata"]["forced_skill_ids"], "brainstorming")
        self.assertEqual(trace["metadata"]["model"], "gpt-test")
        self.assertTrue(started[0]["ended"])
        self.assertEqual(
            started[1],
            {
                "trace_tags": {
                    "trace_id": "trace:chat-1:msg-1",
                    "tags": ["owui", "system"],
                }
            },
        )
        self.assertEqual(started[2], {"flushed": True})


if __name__ == "__main__":
    unittest.main()
