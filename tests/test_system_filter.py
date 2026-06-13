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
    def test_hindsight_bankid_comes_from_user_valve_only(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_._fetch_policy = lambda: "GLOBAL POLICY"

        user = {
            "id": "user-123",
            "email": "geoff@example.com",
            "name": "Geoff User",
            "valves": {"hindsight_bankid": "geoff-bank"},
        }
        body = {"messages": [{"role": "user", "content": "Salut"}]}

        result = filter_.inlet(body, __user__=user)

        content = result["messages"][0]["content"]
        self.assertIn("GLOBAL POLICY", content)
        self.assertIn("[Hindsight MCP]", content)
        self.assertIn("bankid: geoff-bank", content)
        self.assertNotIn("Geoff User", content)
        self.assertNotIn("geoff@example.com", content)
        self.assertNotIn("user-123", content)

    def test_hindsight_bankid_supports_user_valves_object(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_._fetch_policy = lambda: "GLOBAL POLICY"

        class UserValves:
            hindsight_bankid = "alice-bank"

        body = {"messages": [{"role": "user", "content": "Hello"}]}
        result = filter_.inlet(body, __user__={"valves": UserValves()})

        self.assertIn("bankid: alice-bank", result["messages"][0]["content"])

    def test_missing_user_bankid_disables_hindsight_mcp_memory(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_._fetch_policy = lambda: "GLOBAL POLICY"

        body = {"messages": [{"role": "user", "content": "Hello"}]}
        result = filter_.inlet(
            body,
            __user__={"id": "user-123", "email": "geoff@example.com", "name": "Geoff"},
        )

        content = result["messages"][0]["content"]
        self.assertIn("GLOBAL POLICY", content)
        self.assertIn("Do not call Hindsight memory tools", content)
        self.assertNotIn("bankid: Geoff", content)
        self.assertNotIn("bankid: geoff@example.com", content)
        self.assertNotIn("bankid: user-123", content)

    def test_filter_has_no_direct_hindsight_http_configuration(self):
        module = load_filter_module()
        filter_ = module.Filter()

        self.assertFalse(hasattr(filter_, "_fetch_hindsight_memory"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_host"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_path"))
        self.assertFalse(hasattr(filter_.valves, "hindsight_auth_header"))

    def test_existing_system_prompt_is_preserved_after_injections(self):
        module = load_filter_module()
        filter_ = module.Filter()
        filter_._fetch_policy = lambda: "GLOBAL POLICY"

        body = {
            "messages": [
                {"role": "system", "content": "Existing model policy."},
                {"role": "user", "content": "Hello"},
            ]
        }

        result = filter_.inlet(
            body, __user__={"name": "Alice", "valves": {"hindsight_bankid": "Alice"}}
        )

        self.assertEqual(result["messages"][0]["role"], "system")
        content = result["messages"][0]["content"]
        self.assertTrue(content.startswith("GLOBAL POLICY"))
        self.assertIn("[Hindsight MCP]", content)
        self.assertIn("bankid: Alice", content)
        self.assertTrue(content.endswith("Existing model policy."))


if __name__ == "__main__":
    unittest.main()
