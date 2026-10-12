"""Offline LLM transport tests; config and HTTP are replaced before use."""
import contextlib
import importlib.util
import io
import pathlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


CONFIG = types.ModuleType("config")
CONFIG.LLM_ENDPOINT = ""
CONFIG.LLM_API_KEY = "fictional-test-key"
CONFIG.LLM_MODEL = "fictional-model"
CONFIG.LLM_TIMEOUT = 25
CONFIG.STT_SYSTEM_PROMPT = "format transcript"
CONFIG.DEFAULT_TRANSLATE_EN_PROMPT = "translate"
CONFIG.DEFAULT_AI_TASK_PROMPT = "task"
CONFIG.DEFAULT_AI_TASK_EN_PROMPT = "task in English"

path = pathlib.Path(__file__).resolve().parents[1] / "src" / "llm_normalizer.py"
spec = importlib.util.spec_from_file_location("transport_normalizer", path)
LLM = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"config": CONFIG}):
    spec.loader.exec_module(LLM)


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.reply = Mock(ok=True, status_code=200)
        self.reply.json.return_value = {
            "choices": [{"message": {"content": "Formatted transcript."}, "finish_reason": "stop"}]
        }
        self.real_post = LLM.requests.post
        self.post_patch = patch.object(LLM.requests, "post", return_value=self.reply)
        self.post = self.post_patch.start()
        self.normalizer = LLM.LLMNormalizer()
        CONFIG.LLM_API_KEY = "fictional-test-key"

    def tearDown(self):
        self.post_patch.stop()
        self.redirect.__exit__(None, None, None)

    def test_external_http_is_rejected_before_any_request(self):
        for endpoint in (
            "http://provider.example/v1/chat/completions",
            "http://192.168.1.10:11434/v1/chat/completions",
            "http://0.0.0.0:11434/v1/chat/completions",
            "http://[::]:11434/v1/chat/completions",
        ):
            with self.subTest(endpoint=endpoint):
                CONFIG.LLM_ENDPOINT = endpoint
                self.assertEqual(self.normalizer.normalize("original transcript"), "original transcript")
                self.post.assert_not_called()
        self.assertIn("HTTPS", self.output.getvalue())
        self.assertNotIn(CONFIG.LLM_API_KEY, self.output.getvalue())
        self.assertNotIn("original transcript", self.output.getvalue())

    def test_https_sends_transcript_with_existing_auth_and_timeout(self):
        CONFIG.LLM_ENDPOINT = "https://provider.example/v1/chat/completions"
        self.assertEqual(self.normalizer.normalize("original transcript"), "Formatted transcript.")
        args, kwargs = self.post.call_args
        self.assertEqual(args, (CONFIG.LLM_ENDPOINT,))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer fictional-test-key")
        self.assertEqual(kwargs["timeout"], 25)
        self.assertEqual(kwargs["json"]["messages"][1]["content"], "Raw transcript to process:\noriginal transcript")
        self.assertFalse(kwargs.get("allow_redirects", True))
        self.assertNotEqual(kwargs.get("verify"), False)

    def test_local_http_remains_available_without_api_key(self):
        CONFIG.LLM_API_KEY = ""
        for endpoint in (
            "http://localhost:11434/v1/chat/completions",
            "http://LOCALHOST:11434/v1/chat/completions",
            "http://127.0.0.1:11434/v1/chat/completions",
            "http://127.0.0.2:11434/v1/chat/completions",
            "http://[::1]:11434/v1/chat/completions",
        ):
            with self.subTest(endpoint=endpoint):
                CONFIG.LLM_ENDPOINT = endpoint
                self.post.reset_mock()
                self.assertEqual(self.normalizer.normalize("local transcript"), "Formatted transcript.")
                self.post.assert_called_once()
                self.assertNotIn("Authorization", self.post.call_args.kwargs["headers"])
                self.assertFalse(self.post.call_args.kwargs.get("allow_redirects", True))
                self.assertEqual(self.post.call_args.kwargs.get("proxies"), {"http": "", "https": "", "all": ""})

    def test_misleading_localhost_urls_are_rejected(self):
        for endpoint in (
            "http://localhost.provider.example/v1",
            "http://localhost@example.com/v1",
            "http://provider.example@localhost/v1",
            "http://provider.example\\@localhost/v1",
            "http://localhost\\provider.example/v1",
            "http://127.0.0.1.provider.example/v1",
            "http://%6cocalhost/v1",
            "http://local\nhost/v1",
        ):
            with self.subTest(endpoint=endpoint):
                CONFIG.LLM_ENDPOINT = endpoint
                self.assertEqual(self.normalizer.normalize("original"), "original")
                self.post.assert_not_called()

    def test_malformed_or_unsupported_endpoints_are_rejected(self):
        for endpoint in (
            "ftp://localhost/v1", "//localhost/v1", "https:///v1",
            "https://provider.example:bad/v1", "http://[::1/v1",
            "https://user:@example.com/v1",
            "https://:@example.com/v1",
        ):
            with self.subTest(endpoint=endpoint):
                CONFIG.LLM_ENDPOINT = endpoint
                self.assertEqual(self.normalizer.normalize("original"), "original")
                self.post.assert_not_called()

    def test_redirect_is_not_followed_or_accepted_as_a_result(self):
        for endpoint in ("https://provider.example/v1", "http://localhost:11434/v1"):
            with self.subTest(endpoint=endpoint):
                CONFIG.LLM_ENDPOINT = endpoint
                self.reply.status_code = 307
                self.reply.headers = {"Location": "http://provider.example/redirected"}
                self.post.reset_mock()
                self.assertEqual(self.normalizer.normalize("original"), "original")
                self.post.assert_called_once()
                self.assertFalse(self.post.call_args.kwargs.get("allow_redirects", True))

    def test_missing_endpoint_and_empty_text_do_not_make_requests(self):
        CONFIG.LLM_ENDPOINT = ""
        self.assertEqual(self.normalizer.normalize("original"), "original")
        CONFIG.LLM_ENDPOINT = "https://provider.example/v1"
        self.assertEqual(self.normalizer.normalize(""), "")
        self.post.assert_not_called()

    def test_requests_preparation_keeps_local_http_off_external_proxies(self):
        CONFIG.LLM_ENDPOINT = "http://localhost:11434/v1/chat/completions"
        captured = []

        def send(request, **options):
            captured.append((request, options))
            response = LLM.requests.Response()
            response.status_code = 200
            response._content = b'{"choices":[{"message":{"content":"Local result"},"finish_reason":"stop"}]}'
            return response

        # Exercise Requests' real preparation and environment merging, stopping
        # before its network adapter. No auth-profile or secret-file reads.
        with (
            patch.object(LLM.requests, "post", self.real_post),
            patch.object(LLM.requests.sessions.Session, "send", side_effect=send),
            patch.object(LLM.requests.sessions, "get_netrc_auth", return_value=None),
            patch.dict("os.environ", {
                "HTTP_PROXY": "http://proxy.example:8080",
                "HTTPS_PROXY": "http://proxy.example:8080",
                "ALL_PROXY": "http://proxy.example:8080",
                "NO_PROXY": "",
            }),
        ):
            self.assertEqual(self.normalizer.normalize("local text"), "Local result")
        self.assertEqual(len(captured), 1)
        request, options = captured[0]
        self.assertEqual(request.url, CONFIG.LLM_ENDPOINT)
        self.assertFalse(options["allow_redirects"])
        self.assertTrue(options["verify"])
        self.assertFalse(LLM.requests.utils.select_proxy(request.url, options["proxies"]))


if __name__ == "__main__":
    unittest.main()
