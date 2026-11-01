"""« Inventer »: a scenario proposed from a repository and/or a session, in the format of the others, with a free launch word; nothing saved; what was read goes as data."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiwa_brain import config, scen_invent, scen_lib


class InventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for p in (mock.patch.object(config, "SCENARIOS_FILE", Path(self.tmp.name) / "s.json"),
                  mock.patch.object(scen_invent, "_read", return_value={"text": "Dépôt me/app : une appli\n\nREADME : …", "repo": "me/app"})):
            p.start()
            self.addCleanup(p.stop)
        scen_lib.save(config.SCENARIOS_FILE, [{"id": "veille", "name": "Veille", "word": "ma veille", "kind": "double", "prompt": "x", "speak": "", "words": []}])

    def test_a_scenario_is_proposed_in_the_format_of_the_others_and_not_saved(self):
        seen = {}
        reply = json.dumps({"name": "Veille hebdo", "word": "ma veille", "prompt": "Chaque semaine, trouve un article utile sur l'appli et résume-le.", "speak": "Tu ne parles que pour donner l'article.", "words": [{"word": "le lien", "does": "donne le lien"}]})
        out = scen_invent.invent("me/app", None, ask=lambda prompt: (seen.update(prompt=prompt) or reply))
        self.assertTrue(out["ok"])
        sc = out["scenario"]
        self.assertEqual((sc["kind"], sc["name"]), ("double", "Veille hebdo"))
        self.assertNotEqual(scen_lib.plain(sc["word"]), "ma veille")      # taken: it got a number
        self.assertNotIn("Veille hebdo", [x["name"] for x in scen_lib.load(config.SCENARIOS_FILE)])        # nothing saved
        self.assertIn("DONNÉE", seen["prompt"])
        self.assertIn("ma veille", seen["prompt"])

    def test_a_bad_answer_or_no_answer_is_said(self):
        self.assertFalse(scen_invent.invent("me/app", None, ask=lambda p: "pas du json")["ok"])
        self.assertFalse(scen_invent.invent("me/app", None, ask=lambda p: None)["ok"])

    def test_nothing_to_read_is_said(self):
        with mock.patch.object(scen_invent, "_read", return_value={"error": "rien"}):
            self.assertEqual(scen_invent.invent(None, None, ask=lambda p: "{}")["error"], "rien")


if __name__ == "__main__":
    unittest.main()
