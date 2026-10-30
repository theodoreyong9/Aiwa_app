"""The profile: the repository is remembered, the sessions are told what the folder is, and a page is checked against the little it must have."""
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import profile_lib as P


class Profile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = P.PROFILE_FILE
        P.PROFILE_FILE = Path(self.tmp.name) / "profile.json"

    def tearDown(self):
        P.PROFILE_FILE = self.old
        self.tmp.cleanup()

    def test_the_repository_is_remembered_and_only_if_it_is_owner_slash_name(self):
        self.assertIsNone(P.repo())
        self.assertFalse(P.set_repo("pas un depot"))
        self.assertFalse(P.set_repo("a/b; rm -rf"))
        self.assertTrue(P.set_repo("jean/site"))
        self.assertEqual(P.repo(), "jean/site")

    def test_the_description_for_the_other_agent_is_short_and_kept(self):
        P.set_note("cherche un associé " + "x" * 600)
        self.assertEqual(len(P.note()), 400)

    def test_the_sessions_are_told_what_the_folder_is_and_which_repository(self):
        text = P.instruction("jean/site")
        for word in ("Profile/index.html", "jean/site", "data-aiwa-button", "data-aiwa-scenarios", "skills/profile/SKILL.md", "branche par défaut"):
            self.assertIn(word, text)
        self.assertNotIn("jean/site", P.instruction())

    def test_a_page_has_the_short_minimum(self):
        good = '<!doctype html><title>x</title><meta name="viewport" content="width=device-width"><h1>x</h1><video src="media/a.mp4"></video><a href="https://github.com/x">x</a>'
        self.assertEqual(P.check(good), [])
        heavy = good + '<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"></script>'
        self.assertEqual(P.check(heavy), [], "a library from a CDN is the maker's choice")
        bad = P.check('<html><a href="http://x.org/">x</a></html>')
        self.assertGreaterEqual(len(bad), 4)
        self.assertTrue(any("http://" in b for b in bad))

    def test_the_default_home_page_of_the_product_reaches_the_minimum(self):
        html = (Path(__file__).resolve().parents[2] / "web" / "home" / "default.html").read_text(encoding="utf-8")
        self.assertEqual([p for p in P.check(html) if "lien" not in p.lower()], [])


if __name__ == "__main__":
    unittest.main()


class UiFileTest(unittest.TestCase):
    def test_sessions_are_told_how_to_write_the_look_of_the_application(self):
        text = P.instruction()
        self.assertIn("Profile/aiwa-ui.json", text)
        self.assertIn("la barre du bas", text)
        for word in ("match", "zone", "url:https://", "le widget n'est jamais touché"):
            self.assertIn(word, text)
