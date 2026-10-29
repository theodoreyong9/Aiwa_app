import os
import unittest
from unittest import mock

from aiwa_brain import github


class GithubAccountTest(unittest.TestCase):
    def tearDown(self):
        github.TOKEN_FILE.unlink(missing_ok=True)
        github.USER_FILE.unlink(missing_ok=True)

    def test_a_good_token_finds_its_account(self):
        with mock.patch.object(github, "api", return_value={"login": "me"}):
            github.set_token("ghp_" + "a" * 30)
        self.assertEqual(github.connected_user(), "me")
        self.assertEqual(github.checkout_owner() if not os.environ.get("AIWA_GITHUB_OWNER") else "me", "me")

    def test_a_refused_token_is_not_kept(self):
        with mock.patch.object(github, "api", side_effect=github.GithubError("GitHub 401")):
            with self.assertRaises(github.GithubError):
                github.set_token("ghp_" + "b" * 30)
        self.assertIsNone(github.token_value())
        self.assertIsNone(github.connected_user())

    def test_clearing_forgets_the_account(self):
        with mock.patch.object(github, "api", return_value={"login": "me"}):
            github.set_token("ghp_" + "c" * 30)
        github.set_token("")
        self.assertIsNone(github.connected_user())



class TrustFolderTest(unittest.TestCase):
    def test_the_folder_is_trusted_without_touching_the_rest(self):
        import json
        from pathlib import Path
        config_file = Path.home() / ".claude.json"
        config_file.write_text(json.dumps({"theme": "dark", "projects": {"/other": {"hasTrustDialogAccepted": True}}}), encoding="utf-8")
        try:
            github.trust_folder(Path("/work/chat"))
            data = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertTrue(data["projects"]["/work/chat"]["hasTrustDialogAccepted"])
            self.assertEqual((data["theme"], data["projects"]["/other"]), ("dark", {"hasTrustDialogAccepted": True}))
            github.trust_folder(Path("/work/chat"))      # twice: nothing changes
        finally:
            config_file.unlink(missing_ok=True)


class RateLimitTest(unittest.TestCase):
    def tearDown(self):
        github._blocked_until = 0.0
        github._etags.clear()

    def test_an_unchanged_answer_is_served_from_memory_and_the_limit_stops_the_questions(self):
        import io
        import urllib.error

        class Reply(io.BytesIO):
            headers = {"ETag": '"v1"'}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        calls = []

        def opener(request, timeout=0):
            calls.append(dict(request.header_items()))
            if len(calls) == 1:
                return Reply(b'{"a": 1}')
            if len(calls) == 2:
                raise urllib.error.HTTPError("u", 304, "same", {}, None)
            raise urllib.error.HTTPError("u", 403, "limit", {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}, None)

        with mock.patch("urllib.request.urlopen", opener):
            self.assertEqual(github.api("/x"), {"a": 1})
            self.assertEqual(github.api("/x"), {"a": 1})                    # 304: the same data, no cost
            self.assertIn("If-none-match", calls[1])
            with self.assertRaises(github.GithubError) as caught:
                github.api("/y")
            self.assertTrue(caught.exception.limited)
            before = len(calls)
            with self.assertRaises(github.GithubError):
                github.api("/z")
            self.assertEqual(len(calls), before, "nothing is asked while the limit lasts")

if __name__ == "__main__":
    unittest.main()
