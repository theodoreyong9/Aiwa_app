"""Scenarios (pure): launch words, special words, the double's charter and reply."""
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import scen_lib as sc

TMP = Path(tempfile.mkdtemp(prefix="aiwa-scen-"))


class ScenarioLogic(unittest.TestCase):
    def test_the_defaults_are_valid_and_the_report_is_one_of_them(self):
        for d in sc.DEFAULTS:
            self.assertIsNotNone(sc.clean(d), d["id"])
        self.assertEqual(sc.match("fais le rapport", [dict(d) for d in sc.DEFAULTS])["kind"], "report")

    def test_deleting_a_default_is_remembered(self):
        path = TMP / "old.json"
        sc.save(path, [d for d in sc.DEFAULTS if d["id"] != "candidature"])
        sc.save(path, [x for x in sc.load(path) if x["id"] != "candidature"])
        self.assertNotIn("candidature", [x["id"] for x in sc.load(path)])

    def test_launch_word_matches_without_accents_and_longest_wins(self):
        items = [dict(d) for d in sc.DEFAULTS]
        self.assertEqual(sc.match("Lance le scénario entretien s'il te plaît", items)["id"], "entretien")
        self.assertIsNone(sc.match("bonjour", items))

    def test_a_short_launch_word_is_refused(self):
        self.assertIsNone(sc.clean({"name": "x", "word": "oui", "prompt": "p"}))
        self.assertIsNone(sc.clean({"name": "x", "word": "lancer", "prompt": ""}))
        self.assertEqual(sc.clean({"name": "Cours", "word": "mode cours", "prompt": "p"})["id"], "cours")

    def test_special_words_are_tagged_for_the_double(self):
        s = sc.DEFAULTS[0]
        self.assertIn("[mot spécial : scène]", sc.user_turn(s, "Alors, scène"))
        self.assertNotIn("mot spécial", sc.user_turn(s, "il parle du budget"))

    def test_the_charter_gives_the_prompt_the_words_and_the_reply_command_with_the_same_shape_as_the_agent(self):
        text = sc.charter(sc.DEFAULTS[0], "https://ntfy.sh/x")
        for word in ("ta position", "Title: aiwa-scenario", '"scenario":"entretien"', "Tu ne parles à voix haute que quand je dis", '"repo":', "https://ntfy.sh/x"):
            self.assertIn(word, text)
        self.assertNotIn("connector", text)
        self.assertNotIn("boucles", text)

    def test_same_launch_word_twice_is_refused(self):
        _items, _s, err = sc.upsert([dict(d) for d in sc.DEFAULTS], {"name": "Autre", "word": "le rapport", "prompt": "p"})
        self.assertIn("déjà pris", err)


if __name__ == "__main__":
    unittest.main()
