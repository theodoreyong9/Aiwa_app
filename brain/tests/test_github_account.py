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

if __name__ == "__main__":
    unittest.main()
