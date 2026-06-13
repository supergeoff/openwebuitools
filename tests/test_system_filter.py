import importlib.util
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

        result = filter_.inlet(body, __user__=user)

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
        result = filter_.inlet(body, __user__={"valves": UserValves()})

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
        result = filter_.inlet(
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
        result = filter_.inlet(
            body, __user__={"name": "Alice", "valves": {"hindsight_bankid": "Alice"}}
        )

        self.assertEqual(result["messages"][0]["role"], "system")
        content = result["messages"][0]["content"]
        self.assertTrue(content.startswith("GLOBAL POLICY Alice"))
        self.assertTrue(content.endswith("Existing model policy."))


if __name__ == "__main__":
    unittest.main()
