"""The person's way of speaking: only counts are kept, the note appears after a few utterances, and it can be switched off or emptied."""
import json
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import style_lib as st

SAID = ["ouais du coup t'as vu le truc", "bon j'veux que tu regardes ça s'il te plaît", "en fait y'a un souci tu peux voir", "du coup merci",
        "alors t'as fini", "bah ouais regarde", "ben du coup j'sais pas", "tu peux faire ça", "du coup voilà merci"]


class StyleTests(unittest.TestCase):
    def make(self):
        return st.Style(Path(tempfile.mkdtemp()) / "style.json")

    def test_nothing_is_said_before_enough_utterances(self):
        s = self.make()
        s.observe("bonjour")
        self.assertEqual(s.note(), "")

    def test_the_note_describes_the_register_and_the_little_words(self):
        s = self.make()
        for t in SAID:
            s.observe(t)
        note = s.note()
        self.assertIn("tutoiement", note)
        self.assertIn("du coup", note)
        self.assertIn("familier", note)

    def test_the_file_holds_counts_and_never_the_sentences(self):
        s = self.make()
        for t in SAID:
            s.observe(t + " Marie Dupont 0791234567")
        raw = s.path.read_text(encoding="utf-8")
        self.assertNotIn("Dupont", raw)
        self.assertNotIn("0791234567", raw)
        self.assertEqual(oct(s.path.stat().st_mode & 0o777), "0o600")

    def test_off_means_nothing_is_kept_and_nothing_is_said(self):
        s = self.make()
        s.set_enabled(False)
        for t in SAID:
            s.observe(t)
        self.assertEqual(s.status()["count"], 0)
        s.set_enabled(True)
        for t in SAID:
            s.observe(t)
        self.assertTrue(s.status()["ready"])
        s.clear()
        self.assertEqual(s.note(), "")
        self.assertEqual(json.loads(s.path.read_text(encoding="utf-8"))["utt"], 0)


if __name__ == "__main__":
    unittest.main()
