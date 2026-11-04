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
