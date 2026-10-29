import unittest
from unittest import mock

from aiwa_brain import github, github_login


class DeviceFlowTest(unittest.TestCase):
    def tearDown(self):
        github_login.cancel()
        github.TOKEN_FILE.unlink(missing_ok=True)
        github.USER_FILE.unlink(missing_ok=True)

    def test_the_code_is_shown_then_the_token_is_kept(self):
        calls = []

        def post(path, form):
            calls.append(path)
            if path == "/login/device/code":
                return {"device_code": "dev", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device", "interval": 0, "expires_in": 30}
            return {"access_token": "gho_" + "x" * 30}

        with mock.patch.object(github, "api", return_value={"login": "me"}), mock.patch("time.sleep"):
            out = github_login.start(post, background=False)
            self.assertEqual((out["ok"], out["phase"], out["user_code"]), (True, "code", "ABCD-1234"))
            github_login._wait(github_login.flow["id"], "dev", 0, 30, post)
        self.assertEqual(github_login.snapshot()["phase"], "done")
        self.assertEqual(github.connected_user(), "me")

    def test_a_refusal_is_told(self):
        def post(path, form):
            if path == "/login/device/code":
                return {"device_code": "dev", "user_code": "X", "verification_uri": "u", "interval": 0, "expires_in": 30}
            return {"error": "access_denied"}

        with mock.patch("time.sleep"):
            github_login.start(post, background=False)
            github_login._wait(github_login.flow["id"], "dev", 0, 30, post)
        self.assertEqual(github_login.snapshot()["phase"], "failed")
        self.assertIn("refusé", github_login.snapshot()["message"])

    def test_github_saying_no_to_the_application_is_told(self):
        out = github_login.start(lambda path, form: {"error": "device_flow_disabled"}, background=False)
        self.assertFalse(out["ok"])
        self.assertIn("device flow", out["error"])


if __name__ == "__main__":
    unittest.main()
