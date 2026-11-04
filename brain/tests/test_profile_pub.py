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
        with mock.patch("aiwa_brain.profile.github.put_file") as put, mock.patch.object(profile, "read_aiwa", return_value={}):
            self.assertTrue(profile.publish_pub(PUB)["ok"])
            self.assertTrue(profile.publish_pub(PUB)["unchanged"])
        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args[0][:2], ("me/me", "Profile/aiwa.json"))

    def test_the_other_keys_of_the_file_are_kept(self):
        old = {"v": 1, "adaptable": True, "traits": {"couleurs": ["rouge"]}}
        with mock.patch("aiwa_brain.profile.github.put_file") as put, mock.patch.object(profile, "read_aiwa", return_value=old):
            self.assertTrue(profile.publish_pub(PUB)["ok"])
        written = json.loads(put.call_args[0][2])
        self.assertEqual((written["pub"], written["adaptable"], written["traits"]), (PUB, True, {"couleurs": ["rouge"]}))

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


class ProfileSeenTest(ProfilePubTest):
    def test_the_list_is_written_when_it_changed_and_not_more_than_once_an_hour(self):
        with mock.patch("aiwa_brain.profile.github.put_file") as put:
            self.assertTrue(profile.publish_seen(["a/one", "b/two", "a/one", "me/me", "pas un depot"])["ok"])
            self.assertTrue(profile.publish_seen(["a/one", "b/two", "a/one", "me/me"])["unchanged"])
            self.assertTrue(profile.publish_seen(["a/one", "b/two", "c/three"])["waiting"])
        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args[0][:2], ("me/me", "Profile/aiwa-seen.json"))
        self.assertEqual(json.loads(put.call_args[0][2])["seen"], ["a/one", "b/two"])
        self.assertFalse(profile.publish_seen([])["ok"])

    def test_reads_the_list_of_a_visited_profile(self):
        reply = io.BytesIO(json.dumps({"v": 1, "seen": ["x/y", "bad name", "her/repo", "z/w"]}).encode())
        with mock.patch("aiwa_brain.profile.urllib.request.urlopen", return_value=mock.MagicMock(__enter__=lambda s: reply, __exit__=lambda *a: False)):
            self.assertEqual(profile.seen_of("her/repo")["seen"], ["x/y", "z/w"])
        with mock.patch("aiwa_brain.profile.urllib.request.urlopen", side_effect=OSError):
            self.assertEqual(profile.seen_of("her/repo")["seen"], [])


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


class NetworkTest(ProfilePubTest):
    def test_lists_are_written_once_each_and_only_names(self):
        with mock.patch("aiwa_brain.profile.github.put_file") as put:
            self.assertTrue(profile.publish_list("favs", ["a/b", "me/me", "bad name"])["ok"])
            self.assertTrue(profile.publish_list("favs", ["a/b", "me/me"])["unchanged"])
            self.assertTrue(profile.publish_list("jumps", ["c/d"])["ok"])
        self.assertEqual([c[0][1] for c in put.call_args_list], ["Profile/aiwa-favorites.json", "Profile/aiwa-jumps.json"])
        self.assertEqual(json.loads(put.call_args_list[0][0][2]), {"v": 1, "favs": ["a/b"]})
        self.assertFalse(profile.publish_list("autre", [])["ok"])

    def test_the_network_deck_mixes_jumps_and_favourites_of_my_favourites(self):
        files = {("f/one", "jumps"): ["x/1", "x/2", "me/me"], ("f/one", "favs"): ["y/1", "f/two"], ("f/two", "jumps"): ["x/1"], ("f/two", "favs"): ["y/1", "z/1"]}
        with mock.patch.object(profile, "list_of", side_effect=lambda repo, kind: files.get((repo, kind), [])):
            out = profile.network(["f/one", "f/two"])
        self.assertEqual(out["deck"][:2], ["x/1", "y/1"])        # mentioned by both friends, first
        self.assertNotIn("me/me", out["deck"])
        self.assertNotIn("f/two", out["deck"])                    # already a favourite
        self.assertEqual((out["read"], out["of"]), (2, 2))
