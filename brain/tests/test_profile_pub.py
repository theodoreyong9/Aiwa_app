import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiwa_brain import profile, profile_lib

PUB = "ab" * 32


class ProfilePubTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        patch = mock.patch.object(profile_lib, "PROFILE_FILE", Path(self.dir.name) / "profile.json")
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.dir.cleanup)
        profile_lib.PROFILE_FILE.write_text(json.dumps({"repo": "me/me"}), encoding="utf-8")

    def test_written_once(self):
        with mock.patch("aiwa_brain.profile.github.put_file") as put:
            self.assertTrue(profile.publish_pub(PUB)["ok"])
            self.assertTrue(profile.publish_pub(PUB)["unchanged"])
        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args[0][:2], ("me/me", "Profile/aiwa.json"))

    def test_refuses_a_bad_key_and_no_repo(self):
        self.assertFalse(profile.publish_pub("zz")["ok"])
        profile_lib.PROFILE_FILE.write_text("{}", encoding="utf-8")
        self.assertFalse(profile.publish_pub(PUB)["ok"])

    def test_reads_the_key_of_a_visited_profile(self):
        reply = io.BytesIO(json.dumps({"v": 1, "pub": PUB}).encode())
        with mock.patch("aiwa_brain.profile.urllib.request.urlopen", return_value=mock.MagicMock(__enter__=lambda s: reply, __exit__=lambda *a: False)):
            self.assertEqual(profile.pub_of("her/repo")["pub"], PUB)
        with mock.patch("aiwa_brain.profile.urllib.request.urlopen", side_effect=OSError):
            self.assertIsNone(profile.pub_of("her/repo")["pub"])
        self.assertIsNone(profile.pub_of("not a repo")["pub"])


if __name__ == "__main__":
    unittest.main()


class ProfileContractsTest(ProfilePubTest):
    EVENT = {"id": "e1", "type": "contract-spec", "author": "creator1", "payload": {"name": "Vote", "sourceCode": "x"}}

    def test_written_once_for_the_same_content(self):
        with mock.patch("aiwa_brain.profile.github.put_file") as put:
            self.assertTrue(profile.publish_contracts([self.EVENT])["ok"])
            self.assertTrue(profile.publish_contracts([self.EVENT])["unchanged"])
        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args[0][1], "Profile/aiwa-contracts.json")

    def test_refuses_what_is_not_one_persons_contracts(self):
        other = dict(self.EVENT, author="creator2")
        self.assertFalse(profile.publish_contracts([self.EVENT, other])["ok"])
        self.assertFalse(profile.publish_contracts([])["ok"])
        self.assertFalse(profile.publish_contracts([{"type": "burn", "author": "a", "payload": {}}])["ok"])
