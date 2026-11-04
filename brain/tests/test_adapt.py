import json
import unittest
import unittest.mock

from aiwa_brain import adapt, agent, profile


class AdaptBrainTest(unittest.TestCase):
    def test_only_known_keys_and_short_plain_words_are_kept(self):
        out = adapt.clean({"couleurs": ["Rouge", "noir", "<b>", ""], "ton": "Sobre", "mode": ["x"], "inconnu": ["x"], "themes": ["vidéo"] * 20})
        self.assertEqual(out["couleurs"], ["rouge", "noir", "b"])
        self.assertEqual(out["ton"], "sobre")
        self.assertNotIn("mode", out)
        self.assertNotIn("inconnu", out)
        self.assertEqual(out["themes"], ["vidéo"])

    def test_the_traits_come_from_the_model_once_and_an_empty_description_asks_nothing(self):
        with unittest.mock.patch.object(agent, "_model", return_value='{"couleurs":["rouge"],"langues":["fr"]}') as model:
            self.assertEqual(adapt.derive("J'adore le rouge")["traits"], {"couleurs": ["rouge"], "langues": ["fr"]})
            self.assertEqual(adapt.derive("  ")["traits"], {})
        self.assertEqual(model.call_count, 1)
        with unittest.mock.patch.object(agent, "_model", return_value=None):
            self.assertFalse(adapt.derive("x")["ok"])

    def test_the_switch_is_written_in_the_file_of_the_profile(self):
        with unittest.mock.patch.object(profile, "update_aiwa", return_value={"ok": True}) as update:
            self.assertTrue(adapt.publish(True)["ok"])
        self.assertEqual(update.call_args[0][0], {"v": 1, "adaptable": True})


class DictatedRulesTest(unittest.TestCase):
    PAGE = b"<html><body><h1 class='titre'>Moi</h1><p id='intro'>Bonjour</p></body></html>"
    MODEL = ('{"dit":"Si le visiteur aime le rouge, mon titre devient rouge","si":{"traits.couleurs":{"contient":"Rouge"}},'
             '"alors":[{"zone":"titre","couleur":"{traits.couleurs.0}","javascript":"evil()"}],"zones":{"titre":{"selecteur":"h1.titre","modifiable":["couleur","texte"]}}}')

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        adapt.RULES_FILE = Path(self.dir.name) / "rules.json"
        self.put = unittest.mock.patch.object(adapt.github, "put_file").start()
        self.update = unittest.mock.patch.object(adapt.profile, "update_aiwa", return_value={"ok": True}).start()
        unittest.mock.patch.object(adapt.profile_lib, "repo", return_value="me/me").start()
        unittest.mock.patch.object(adapt.relay, "raw_get", return_value=self.PAGE).start()
        self.addCleanup(unittest.mock.patch.stopall)

    def test_a_sentence_becomes_a_rule_the_zones_and_the_files(self):
        with unittest.mock.patch.object(agent, "_model", return_value=self.MODEL):
            out = adapt.add_rule("si le visiteur aime le rouge mon titre devient rouge")
        self.assertTrue(out["ok"])
        listed = adapt.rules()
        self.assertEqual((len(listed), listed[0]["on"]), (1, True))
        written = json.loads(self.put.call_args[0][2])
        self.assertEqual(written["regles"][0]["si"], {"traits.couleurs": {"contient": "rouge"}})
        self.assertEqual(written["regles"][0]["alors"], [{"zone": "titre", "couleur": "{traits.couleurs.0}"}])      # nothing but the known changes
        self.assertEqual(self.update.call_args[0][0]["zones"], {"titre": {"modifiable": ["couleur"], "selecteur": "h1.titre"}})

    def test_a_rule_that_is_not_understood_is_refused_and_nothing_is_written(self):
        for answer in ('{"erreur":"ce n\'est pas une règle"}', '{"si":{"truc":{"contient":"x"}},"alors":[{"zone":"titre","texte":"x"}]}', "pas du json", None):
            with unittest.mock.patch.object(agent, "_model", return_value=answer):
                self.assertFalse(adapt.add_rule("blabla")["ok"])
        self.assertEqual(adapt.rules(), [])
        self.put.assert_not_called()

    def test_a_rule_is_cut_lit_again_or_removed_by_its_words_and_the_files_follow(self):
        with unittest.mock.patch.object(agent, "_model", return_value=self.MODEL):
            adapt.add_rule("rouge")
        self.assertEqual(adapt.change("rouge", "off")["count"], 1)
        self.assertEqual(json.loads(self.put.call_args[0][2]), {"regles": []})
        self.assertFalse(adapt.rules()[0]["on"])
        adapt.change("rouge", "on")
        self.assertEqual(len(json.loads(self.put.call_args[0][2])["regles"]), 1)
        self.assertFalse(adapt.change("inexistante", "remove")["ok"])
        self.assertEqual(adapt.change("all", "remove")["count"], 1)
        self.assertEqual(adapt.rules(), [])
        self.assertEqual(self.update.call_args[0][0]["zones"], {})

    def test_nothing_is_written_twice(self):
        with unittest.mock.patch.object(agent, "_model", return_value=self.MODEL):
            adapt.add_rule("rouge")
        calls = self.put.call_count
        self.assertTrue(adapt.sync()["unchanged"])
        self.assertEqual(self.put.call_count, calls)

    def test_the_agent_reads_the_rules_of_her_page(self):
        self.assertEqual(adapt.line(), "")
        with unittest.mock.patch.object(agent, "_model", return_value=self.MODEL):
            adapt.add_rule("rouge")
        self.assertIn("mon titre devient rouge", adapt.line())
