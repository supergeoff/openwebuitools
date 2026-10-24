"""Tests for the dictation proxy (services/dictee/app.py)."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import httpx
from starlette.testclient import TestClient

APP_PATH = Path(__file__).resolve().parent.parent / "services" / "dictee" / "app.py"
SPEACHES = "http://speaches.test/v1"
LITELLM = "http://litellm.test/v1"
RAW = "bonjour je teste la dictée avec docploy et parakit"
CLEAN = "Bonjour, je teste la dictée avec Dokploy et Parakeet."


def load_module():
    spec = importlib.util.spec_from_file_location("dictee_app", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Upstreams:
    """Fake speaches and LiteLLM servers behind one httpx.MockTransport."""

    def __init__(self, speaches=None, llm=None):
        self.speaches = speaches or (lambda req: httpx.Response(200, json={"text": RAW}))
        self.llm = llm or (lambda req: chat_response(CLEAN))
        self.speaches_requests = []
        self.llm_requests = []

    def handler(self, request):
        url = str(request.url)
        if url == f"{SPEACHES}/audio/transcriptions":
            self.speaches_requests.append(request)
            return self.speaches(request)
        if url == f"{LITELLM}/chat/completions":
            self.llm_requests.append(request)
            return self.llm(request)
        return httpx.Response(599, text="unexpected url " + url)


def chat_response(content):
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


class DicteeTestCase(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.glossary = Path(self.tmp.name) / "glossary.txt"

    def tearDown(self):
        self.tmp.cleanup()

    def client(self, upstreams):
        settings = self.mod.Settings(
            speaches_url=SPEACHES,
            litellm_url=LITELLM,
            litellm_api_key="llm-key",
            model="flash-low",
            glossary_file=str(self.glossary),
        )
        app = self.mod.create_app(settings, transport=httpx.MockTransport(upstreams.handler))
        return TestClient(app)

    def post(self, client, body=b"--b\r\naudio\r\n--b--\r\n"):
        return client.post(
            "/v1/audio/transcriptions",
            content=body,
            headers={"Authorization": "Bearer stt-key", "Content-Type": "multipart/form-data; boundary=b"},
        )


class ForwardingTests(DicteeTestCase):
    def test_body_and_headers_are_forwarded_to_speaches(self):
        up = Upstreams()
        with self.client(up) as c:
            self.post(c, body=b"--b\r\nexact bytes\r\n--b--\r\n")
        sent = up.speaches_requests[0]
        self.assertEqual(sent.content, b"--b\r\nexact bytes\r\n--b--\r\n")
        self.assertEqual(sent.headers["authorization"], "Bearer stt-key")
        self.assertEqual(sent.headers["content-type"], "multipart/form-data; boundary=b")

    def test_speaches_error_is_returned_unchanged_without_llm_call(self):
        up = Upstreams(speaches=lambda req: httpx.Response(401, json={"detail": "bad key"}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json(), {"detail": "bad key"})
        self.assertEqual(up.llm_requests, [])

    def test_unreachable_speaches_returns_502(self):
        def boom(req):
            raise httpx.ConnectError("down", request=req)

        up = Upstreams(speaches=boom)
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.status_code, 502)
        self.assertEqual(up.llm_requests, [])

    def test_non_json_response_is_returned_unchanged(self):
        up = Upstreams(speaches=lambda req: httpx.Response(200, text="plain text", headers={"content-type": "text/plain"}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.text, "plain text")
        self.assertEqual(up.llm_requests, [])

    def test_json_without_text_is_returned_unchanged(self):
        up = Upstreams(speaches=lambda req: httpx.Response(200, json={"segments": []}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.json(), {"segments": []})
        self.assertEqual(up.llm_requests, [])


class ThresholdTests(DicteeTestCase):
    def test_short_text_is_returned_raw(self):
        up = Upstreams(speaches=lambda req: httpx.Response(200, json={"text": "oui merci beaucoup"}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.json()["text"], "oui merci beaucoup")
        self.assertEqual(up.llm_requests, [])

    def test_long_text_is_returned_raw(self):
        long_text = " ".join(["mot"] * 401)
        up = Upstreams(speaches=lambda req: httpx.Response(200, json={"text": long_text}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.json()["text"], long_text)
        self.assertEqual(up.llm_requests, [])


class CleanupTests(DicteeTestCase):
    def test_cleaned_text_replaces_only_text_field(self):
        up = Upstreams(speaches=lambda req: httpx.Response(200, json={"text": RAW, "language": "fr", "duration": 3.2}))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.json(), {"text": CLEAN, "language": "fr", "duration": 3.2})

    def test_llm_request_payload(self):
        up = Upstreams()
        with self.client(up) as c:
            self.post(c)
        req = up.llm_requests[0]
        self.assertEqual(req.headers["authorization"], "Bearer llm-key")
        payload = json.loads(req.content)
        self.assertEqual(payload["model"], "flash-low")
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Never change the meaning", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][1], {"role": "user", "content": f"<transcript>\n{RAW}\n</transcript>"})

    def test_transcript_wrapper_in_answer_is_removed(self):
        up = Upstreams(llm=lambda req: chat_response(f"<transcript>\n{CLEAN}\n</transcript>"))
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.json()["text"], CLEAN)


class FallbackTests(DicteeTestCase):
    def assert_raw(self, llm):
        up = Upstreams(llm=llm)
        with self.client(up) as c:
            r = self.post(c)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], RAW)

    def test_llm_http_error(self):
        self.assert_raw(lambda req: httpx.Response(500, json={"error": "boom"}))

    def test_llm_timeout(self):
        def slow(req):
            raise httpx.ReadTimeout("slow", request=req)

        self.assert_raw(slow)

    def test_llm_malformed_answer(self):
        self.assert_raw(lambda req: httpx.Response(200, json={"unexpected": True}))

    def test_llm_empty_answer(self):
        self.assert_raw(lambda req: chat_response("   "))

    def test_llm_answer_too_short(self):
        self.assert_raw(lambda req: chat_response("Oui."))

    def test_llm_answer_too_long(self):
        self.assert_raw(lambda req: chat_response(CLEAN * 3))


class GlossaryTests(DicteeTestCase):
    def system_prompt(self):
        up = Upstreams()
        with self.client(up) as c:
            self.post(c)
        return json.loads(up.llm_requests[0].content)["messages"][0]["content"]

    def test_glossary_terms_are_appended(self):
        self.glossary.write_text("# termes\n\nDokploy\n  speaches (often heard as: speech)  \nParakeet\n", encoding="utf-8")
        self.assertTrue(
            self.system_prompt().endswith("\nGlossary:\n- Dokploy\n- speaches (often heard as: speech)\n- Parakeet")
        )

    def test_missing_glossary_adds_no_line(self):
        self.assertNotIn("Glossary:", self.system_prompt())

    def test_glossary_is_reread_on_each_request(self):
        self.glossary.write_text("Dokploy\n", encoding="utf-8")
        up = Upstreams()
        with self.client(up) as c:
            self.post(c)
            self.glossary.write_text("Dokploy\nLangfuse\n", encoding="utf-8")
            self.post(c)
        second = json.loads(up.llm_requests[1].content)["messages"][0]["content"]
        self.assertTrue(second.endswith("Glossary:\n- Dokploy\n- Langfuse"))


class RoutesAndLogsTests(DicteeTestCase):
    def test_health(self):
        with self.client(Upstreams()) as c:
            r = c.get("/health")
        self.assertEqual(r.status_code, 200)

    def test_unknown_route_is_404(self):
        with self.client(Upstreams()) as c:
            r = c.get("/v1/models")
        self.assertEqual(r.status_code, 404)

    def test_logs_never_contain_the_transcript(self):
        up = Upstreams()
        with self.assertLogs("dictee", level="INFO") as logs:
            with self.client(up) as c:
                self.post(c)
        joined = "\n".join(logs.output)
        self.assertIn("decision=cleaned", joined)
        self.assertNotIn("docploy", joined)
        self.assertNotIn("Dokploy", joined)

    def test_fallback_is_a_single_warning_line(self):
        up = Upstreams(llm=lambda req: httpx.Response(500))
        with self.assertLogs("dictee", level="INFO") as logs:
            with self.client(up) as c:
                self.post(c)
        warnings = [r for r in logs.records if r.levelname == "WARNING"]
        self.assertEqual(len(warnings), 1)
        self.assertIn("decision=llm_failed", warnings[0].getMessage())
        self.assertIsNone(warnings[0].exc_info)


if __name__ == "__main__":
    unittest.main()
