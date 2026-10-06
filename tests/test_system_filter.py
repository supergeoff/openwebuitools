import importlib.util
import asyncio
import contextlib
import hashlib
import inspect
import json
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


def span_attributes(span):
    """Decode OTLP JSON attributes back to plain Python values."""

    def decode(value):
        if "arrayValue" in value:
            return [decode(item) for item in value["arrayValue"].get("values", [])]
        if "intValue" in value:
            return int(value["intValue"])
        for key in ("stringValue", "boolValue", "doubleValue"):
            if key in value:
                return value[key]
        raise AssertionError(f"unexpected OTLP value {value}")

    return {item["key"]: decode(item["value"]) for item in span["attributes"]}


@contextlib.contextmanager
def fake_httpx(calls, status_code=200, payload=None):
    """Stand-in for httpx.AsyncClient that records POST requests."""

    class Response:
        def __init__(self):
            self.status_code = status_code
            self.text = json.dumps(payload or {})
            self.headers = {}

        def json(self):
            return payload or {}

    class AsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, auth=None, headers=None):
            calls.append({"url": url, "json": json, "auth": auth, "headers": headers})
            return Response()

    module = types.ModuleType("httpx")
    module.AsyncClient = AsyncClient
    original = sys.modules.get("httpx")
    sys.modules["httpx"] = module
    try:
        yield
    finally:
        if original is None:
            sys.modules.pop("httpx", None)
        else:
            sys.modules["httpx"] = original


class SystemFilterTest(unittest.TestCase):
    def test_prompt_modules_compile_without_user_data(self):
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
        }
        body = {"messages": [{"role": "user", "content": "Salut"}]}

        result = run_inlet(filter_, body, __user__=user)

        self.assertEqual(calls, [{}])
        content = result["messages"][0]["content"]
        self.assertEqual(content, "GLOBAL POLICY")
        self.assertNotIn("Geoff User", content)
        self.assertNotIn("geoff@example.com", content)
        self.assertNotIn("user-123", content)

    def test_filter_has_no_hindsight_configuration(self):
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
        self.assertFalse(hasattr(filter_, "user_valves"))

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
        result = run_inlet(filter_, body, __user__={"name": "Alice"})

        self.assertEqual(result["messages"][0]["role"], "system")
        content = result["messages"][0]["content"]
        self.assertTrue(content.startswith("GLOBAL POLICY"))
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

    def test_builtin_prompt_modules_follow_default_prompt_sections(self):
        module = load_filter_module()
        filter_ = module.Filter()

        self.assertEqual(
            filter_._prompt_module_names(),
            ["output_style", "tools", "memory", "skills", "task_management"],
        )

    def test_builtin_prompt_modules_have_a_prompt_file(self):
        module = load_filter_module()

        for name in module.PROMPT_MODULES:
            self.assertTrue((ROOT / "prompts" / f"{name}.md").exists(), name)

    def test_split_prompts_assemble_in_declaration_order(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("output_style", "tools", "memory", "skills")
        filter_ = module.Filter()
        calls = []

        class Prompt:
            compile_calls = []

            def __init__(self, name):
                self.name = name

            def compile(self, **kwargs):
                self.compile_calls.append((self.name, kwargs))
                return f"# {self.name}\n\n{self.name} body"

        class Client:
            def get_prompt(self, name, **kwargs):
                calls.append((name, kwargs))
                return Prompt(name)

        filter_._client = Client()

        result = run_inlet(
            filter_,
            {"messages": [{"role": "user", "content": "Hello"}]},
        )

        # Fetches run concurrently; only the set of fetched modules is
        # deterministic, the assembled section order is asserted below.
        self.assertEqual(
            sorted(name for name, _ in calls),
            sorted(["output_style", "tools", "memory", "skills"]),
        )
        self.assertEqual(
            [kwargs["label"] for _, kwargs in calls],
            ["production", "production", "production", "production"],
        )
        self.assertEqual(sorted(Prompt.compile_calls), sorted([
            ("output_style", {}),
            ("tools", {}),
            ("memory", {}),
            ("skills", {}),
        ]))
        self.assertEqual(
            result["messages"][0]["content"],
            "# output_style\n\noutput_style body\n\n"
            "# tools\n\ntools body\n\n"
            "# memory\n\nmemory body\n\n"
            "# skills\n\nskills body",
        )

    def test_missing_langfuse_keys_hard_fail_when_prompt_enabled(self):
        module = load_filter_module()
        filter_ = module.Filter()

        with self.assertRaisesRegex(RuntimeError, "Langfuse public and secret keys"):
            run_inlet(filter_, {"messages": [{"role": "user", "content": "Hello"}]})

    def test_langfuse_prompt_fetch_failure_hard_fails_with_module_name(self):
        module = load_filter_module()
        module.PROMPT_MODULES = ("tools",)
        filter_ = module.Filter()

        class Client:
            def get_prompt(self, name, **kwargs):
                raise ValueError("not found")

        filter_._client = Client()

        with self.assertRaisesRegex(RuntimeError, "tools.*production.*not found"):
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

    def test_trace_and_observation_ids_follow_langfuse_sdk_algorithms(self):
        module = load_filter_module()
        filter_ = module.Filter()

        seed = "owui-chat-1-message-2"
        self.assertEqual(
            filter_._build_trace_id("chat-1", "message-2"),
            hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex(),
        )
        self.assertEqual(
            filter_._root_observation_id("chat-1", "message-2"),
            hashlib.sha256(f"{seed}:root".encode("utf-8")).digest()[:8].hex(),
        )
        self.assertEqual(len(filter_._build_trace_id("chat-1", "message-2")), 32)
        self.assertEqual(len(filter_._request_observation_id("chat-1", "message-2")), 16)

    def test_inlet_exports_request_event_with_trace_attributes(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enabled = False
        captured = []
        filter_._spawn_export = lambda spans: captured.extend(spans)

        run_inlet(
            filter_,
            {
                "model": "gpt-test",
                "messages": [{"role": "user", "content": "Question"}],
            },
            __user__={"id": "user-1", "email": "geoff@example.com"},
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
        )

        self.assertEqual(len(captured), 1)
        span = captured[0]
        self.assertEqual(span["name"], "owui-chat-request")
        self.assertEqual(span["traceId"], filter_._build_trace_id("chat-1", "msg-1"))
        self.assertEqual(span["spanId"], filter_._request_observation_id("chat-1", "msg-1"))
        self.assertEqual(
            span["parentSpanId"], filter_._root_observation_id("chat-1", "msg-1")
        )
        self.assertEqual(span["startTimeUnixNano"], span["endTimeUnixNano"])
        attributes = span_attributes(span)
        self.assertEqual(attributes["langfuse.trace.name"], "owui-chat")
        self.assertEqual(attributes["langfuse.user.id"], "geoff@example.com")
        self.assertEqual(attributes["langfuse.session.id"], "chat-1")
        self.assertEqual(attributes["langfuse.trace.tags"], ["owui", "system"])
        self.assertEqual(attributes["langfuse.observation.type"], "event")
        self.assertEqual(
            json.loads(attributes["langfuse.observation.input"]),
            {"last_user_message": "Question"},
        )
        self.assertEqual(attributes["langfuse.observation.metadata.status"], "pending")
        self.assertEqual(attributes["langfuse.trace.metadata.model"], "gpt-test")
        self.assertEqual(
            attributes["langfuse.trace.metadata.owui_trace_key"], "owui-chat-1-msg-1"
        )
        self.assertNotIn("langfuse.trace.input", attributes)

    def test_inlet_skips_tracing_for_temporary_chats(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enabled = False
        captured = []
        filter_._spawn_export = lambda spans: captured.extend(spans)

        run_inlet(
            filter_,
            {"messages": [{"role": "user", "content": "Hello"}]},
            __user__={"id": "user-1"},
            __metadata__={"chat_id": "local:socket-1", "message_id": "msg-1"},
        )

        self.assertEqual(captured, [])

    def test_inlet_skips_tracing_without_chat_or_message_id(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enabled = False
        captured = []
        filter_._spawn_export = lambda spans: captured.extend(spans)

        run_inlet(
            filter_,
            {"messages": [{"role": "user", "content": "Hello"}]},
            __user__={"id": "user-1"},
        )

        self.assertEqual(captured, [])

    def test_outlet_exports_complete_root_span_with_prompt_metadata(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.enabled = False
        filter_.valves.forced_tool_ids = "server:mcp:memory"
        filter_.valves.forced_skill_ids = "brainstorming"
        captured = []
        filter_._spawn_export = lambda spans: captured.extend(spans)
        metadata = {"chat_id": "chat-1", "message_id": "msg-1"}
        user = {"id": "user-1", "email": "geoff@example.com"}

        run_inlet(
            filter_,
            {"model": "gpt-test", "messages": [{"role": "user", "content": "Question"}]},
            __user__=user,
            __metadata__=metadata,
        )
        run_outlet(
            filter_,
            {
                "model": "gpt-test",
                "messages": [
                    {"role": "user", "content": "Question"},
                    {"role": "assistant", "content": "Answer"},
                ],
            },
            __user__=user,
            __metadata__=metadata,
        )

        self.assertEqual(len(captured), 2)
        request_event, root = captured
        self.assertEqual(root["name"], "owui-chat")
        self.assertNotIn("parentSpanId", root)
        self.assertEqual(root["traceId"], request_event["traceId"])
        self.assertEqual(root["spanId"], request_event["parentSpanId"])
        self.assertEqual(root["startTimeUnixNano"], request_event["startTimeUnixNano"])
        self.assertGreaterEqual(
            int(root["endTimeUnixNano"]), int(root["startTimeUnixNano"])
        )

        attributes = span_attributes(root)
        self.assertEqual(attributes["langfuse.observation.type"], "span")
        self.assertEqual(
            json.loads(attributes["langfuse.observation.input"]),
            {"last_user_message": "Question"},
        )
        self.assertEqual(
            json.loads(attributes["langfuse.observation.output"]),
            {"assistant_message": "Answer"},
        )
        self.assertEqual(
            attributes["langfuse.trace.output"], attributes["langfuse.observation.output"]
        )
        self.assertEqual(attributes["langfuse.observation.metadata.status"], "completed")
        self.assertEqual(attributes["langfuse.user.id"], "geoff@example.com")
        self.assertEqual(attributes["langfuse.session.id"], "chat-1")
        self.assertEqual(
            attributes["langfuse.trace.metadata.forced_tool_ids"], "server:mcp:memory"
        )
        self.assertEqual(
            attributes["langfuse.trace.metadata.forced_skill_ids"], "brainstorming"
        )
        self.assertEqual(attributes["langfuse.trace.metadata.passthrough"], "false")
        self.assertEqual(filter_._inflight_starts, {})

    def test_outlet_reads_assistant_text_from_structured_output_items(self):
        module = load_filter_module()
        filter_ = module.Filter()
        captured = []
        filter_._spawn_export = lambda spans: captured.extend(spans)

        run_outlet(
            filter_,
            {
                "model": "gpt-test",
                "messages": [
                    {"role": "user", "content": "Question"},
                    {
                        "role": "assistant",
                        "content": "",
                        "output": [
                            {"type": "reasoning", "summary": []},
                            {
                                "type": "message",
                                "content": [
                                    {"type": "output_text", "text": "Answer from"},
                                    {"type": "output_text", "text": " items"},
                                ],
                            },
                        ],
                    },
                ],
            },
            __metadata__={"chat_id": "chat-1", "message_id": "msg-1"},
        )

        attributes = span_attributes(captured[0])
        self.assertEqual(
            json.loads(attributes["langfuse.observation.output"]),
            {"assistant_message": "Answer from items"},
        )

    def test_post_otlp_sends_v4_ingestion_payload(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.langfuse_public_key = "pk-test"
        filter_.valves.langfuse_secret_key = "sk-test"
        filter_._clock_offset = 0.0
        calls = []
        span = filter_._otlp_span(
            trace_id="a" * 32,
            span_id="b" * 16,
            parent_span_id=None,
            name="owui-chat",
            start_ns=1,
            end_ns=2,
            attributes={"langfuse.trace.tags": ["owui"], "count": 3, "flag": True},
        )

        with fake_httpx(calls, status_code=200, payload={"partialSuccess": {}}):
            asyncio.run(filter_._post_otlp([span]))

        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(
            call["url"], "https://langfuse.supergeoff.top/api/public/otel/v1/traces"
        )
        self.assertEqual(call["headers"], {"x-langfuse-ingestion-version": "4"})
        self.assertEqual(call["auth"], ("pk-test", "sk-test"))
        scope_spans = call["json"]["resourceSpans"][0]["scopeSpans"][0]
        self.assertEqual(scope_spans["spans"], [span])
        self.assertEqual(
            span["attributes"],
            [
                {
                    "key": "langfuse.trace.tags",
                    "value": {"arrayValue": {"values": [{"stringValue": "owui"}]}},
                },
                {"key": "count", "value": {"intValue": "3"}},
                {"key": "flag", "value": {"boolValue": True}},
            ],
        )

    def test_post_otlp_raises_when_langfuse_rejects_spans(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_.valves.langfuse_public_key = "pk-test"
        filter_.valves.langfuse_secret_key = "sk-test"
        filter_._clock_offset = 0.0
        payload = {"partialSuccess": {"rejectedSpans": 1, "errorMessage": "bad span"}}

        with fake_httpx([], status_code=200, payload=payload):
            with self.assertRaisesRegex(RuntimeError, "rejected 1 span.*bad span"):
                asyncio.run(filter_._post_otlp([]))

    def test_large_clock_skew_shifts_span_times(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_._clock_offset = 120.0
        spans = [{"startTimeUnixNano": "1000", "endTimeUnixNano": "2000"}]

        filter_._shift_span_times(spans)

        self.assertEqual(spans[0]["startTimeUnixNano"], str(1000 + 120_000_000_000))
        self.assertEqual(spans[0]["endTimeUnixNano"], str(2000 + 120_000_000_000))


if __name__ == "__main__":
    unittest.main()
