"""The style the person picks and the game: one point lost an hour, +10 / -5 for the agent's own proposals, silence at zero, points given by voice."""
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import persona_lib


class PersonaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1_000_000.0]
        self.p = persona_lib.Persona(Path(self.tmp.name) / "p.json", clock=lambda: self.now[0])

    def test_style_is_told_only_when_chosen_and_never_for_the_sessions(self):
        self.assertEqual(self.p.note(), "")
        self.p.set_style("vanneur")
        note = self.p.note()
        self.assertIn("vanneur", note)
        self.assertIn("jamais les messages", note)
        self.p.set_style("inconnu")
        self.assertEqual(self.p.status()["style"], "vanneur")

    def test_one_point_an_hour_and_silence_at_zero(self):
        self.p.set_game(True)
        self.assertEqual(self.p.status()["points"], 48)
        self.now[0] += 5 * 3600 + 100
        self.assertEqual(self.p.status()["points"], 43)
        self.now[0] += 100 * 3600
        self.assertTrue(self.p.muted())

    def test_own_proposal_answered(self):
        self.p.set_game(True)
        self.assertEqual(self.p.reward(True), 58)
        self.assertEqual(self.p.reward(False), 53)

    def test_points_given_by_voice_work_at_zero(self):
        self.p.set_game(True)
        self.now[0] += 100 * 3600
        self.assertTrue(self.p.muted())
        self.assertEqual(self.p.gift_in("allez je te donne 20 points"), 20)
        self.assertFalse(self.p.muted())
        self.assertEqual(self.p.status()["points"], 20)
        self.assertEqual(self.p.gift_in("je te retire 5 points"), -5)
        self.assertEqual(self.p.status()["points"], 15)

    def test_nothing_counts_when_the_game_is_off(self):
        self.assertIsNone(self.p.gift_in("je te donne 20 points"))
        self.assertIsNone(self.p.status()["points"])
        self.assertFalse(self.p.muted())

    def test_kept_across_a_restart(self):
        self.p.set_game(True)
        self.p.set_style("sec")
        again = persona_lib.Persona(Path(self.tmp.name) / "p.json", clock=lambda: self.now[0])
        self.assertEqual((again.status()["style"], again.status()["points"]), ("sec", 48))


if __name__ == "__main__":
    unittest.main()
