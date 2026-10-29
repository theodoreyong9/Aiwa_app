"""« Création à la volée »: the cutting of the stream, the actions, the progress sentences."""
import unittest

from aiwa_brain import live_lib as live


class LiveLogic(unittest.TestCase):
    def test_sentences_come_as_they_are_finished_and_the_marker_cut_in_two_is_still_found(self):
        s = live.Splitter()
        out = []
        for piece in ["Je lance ça. Et je ", "te dis quand c'est prêt.\n@@AC", "TIONS {\"send\":[{\"session\":\"session_A\",\"message\":\"fais x\"}]}"]:
            out += s.feed(piece)
        last, actions = s.finish()
        self.assertEqual(out, ["Je lance ça.", "Et je te dis quand c'est prêt."])
        self.assertEqual(actions["send"][0]["session"], "session_A")
        self.assertNotIn("@@", " ".join(out + last))

    def test_a_repository_is_enough_to_aim_a_message(self):
        actions = live.parse_actions('{"send":[{"repo":"me/app","message":"fais x"},{"message":"sans cible"}]}')
        self.assertEqual(len(actions["send"]), 1)
        self.assertEqual(actions["send"][0]["repo"], "me/app")

    def test_a_reply_without_actions_is_only_said(self):
        s = live.Splitter()
        out = s.feed("D'accord, je regarde ça avec toi.")
        last, actions = s.finish()
        self.assertEqual(out + last, ["D'accord, je regarde ça avec toi."])
        self.assertEqual(actions, {})

    def test_bad_actions_are_ignored_and_never_raise(self):
        self.assertEqual(live.parse_actions("pas du json"), {})
        self.assertEqual(live.parse_actions('{"send":[{"session":"","message":"x"}]}'), {})

    def test_progress_says_the_new_commit_and_the_failed_workflow_but_nothing_on_the_first_look(self):
        self.assertEqual(live.progress({}, {"sha": "a", "ci": "success"}), [])
        out = live.progress({"sha": "a", "ci": "running"}, {"sha": "b", "message": "Ajoute la page", "ci": "failure"})
        self.assertEqual(out, ["Nouveau commit : Ajoute la page.", "Le workflow a échoué."])
        self.assertEqual(live.progress({"sha": "a", "ci": "success"}, {"sha": "a", "ci": "success"}), [])

    def test_the_other_sessions_are_named_in_what_is_said(self):
        out = live.progress({"sha": "a"}, {"sha": "b", "message": "Ajoute la page"}, "Sur la session « Blog » : ")
        self.assertEqual(out, ["Sur la session « Blog » : nouveau commit : Ajoute la page."])

    def test_the_prompt_knows_every_screen_the_agent_may_open(self):
        text = live.system("point")
        for word in ("video", "chambre", "reglages", "scenario"):
            self.assertIn(word, text)


if __name__ == "__main__":
    unittest.main()
