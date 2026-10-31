"""The style the person picks and the race between the person and her agent: 100 each, a point a day, +10/-5, verdicts kept with their reason, gifts as transfers, the end of a round, ten rounds."""
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import persona_lib

DAY = 86400


class PersonaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1_000_000.0]
        self.p = persona_lib.Persona(Path(self.tmp.name) / "p.json", clock=lambda: self.now[0])

    def test_style_is_told_only_when_chosen_and_never_for_the_sessions(self):
        self.assertEqual(self.p.note(), "")
        self.p.set_style("vanneur")
        self.assertIn("jamais les messages", self.p.note())
        self.p.set_style("inconnu")
        self.assertEqual(self.p.status()["style"], "vanneur")

    def test_both_start_at_100_and_lose_a_point_a_day(self):
        self.p.set_game(True)
        self.now[0] += 5 * DAY + 100
        g = self.p.status()["game"]
        self.assertEqual((g["user"], g["agent"]), (95, 95))

    def test_own_proposal_and_verdicts(self):
        self.p.set_game(True)
        self.p.reward(True)
        self.p.reward(False)
        self.p.apply_agent({"verdict": "non", "raison": "pas faisable"})
        self.p.apply_agent({"verdict": "oui"})
        g = self.p.status()["game"]
        self.assertEqual((g["agent"], g["user"]), (105, 105))
        self.assertTrue(any("pas faisable" in h["reason"] for h in g["history"]))

    def test_a_gift_is_a_transfer_and_never_ruins_the_giver(self):
        self.p.set_game(True)
        self.assertEqual(self.p.gift_in("allez je te donne 20 points"), 20)
        g = self.p.status()["game"]
        self.assertEqual((g["user"], g["agent"]), (80, 120))
        self.assertEqual(self.p.give("user", 5000), 79)

    def test_zero_ends_the_round_and_the_other_wins(self):
        self.p.set_game(True)
        self.now[0] += 100 * DAY
        g = self.p.status()["game"]
        self.assertEqual(g["ended"], "draw")        # both at zero on the same day
        self.assertIn("nulle", self.p.pop_event())
        self.assertIsNone(self.p.pop_event())
        self.p.restart()
        self.p.add("agent", -100)
        self.p.add("user", 5)
        self.assertEqual(self.p.status()["game"]["ended"], "user")
        self.assertEqual(self.p.status()["game"]["wins"]["user"], 1)

    def test_after_thirty_days_the_best_wins_only_with_the_minimum(self):
        self.p.set_game(True)
        self.p.add("user", 80)
        self.now[0] += 30 * DAY
        g = self.p.status()["game"]
        self.assertEqual(g["ended"], "user")         # 150 at least (180 - 30 = 150)
        self.p.restart()
        self.p.add("user", 20)
        self.now[0] += 30 * DAY
        self.assertEqual(self.p.status()["game"]["ended"], "draw")      # nobody reached 150

    def test_ten_rounds_make_the_grand_winner_and_a_restart_keeps_the_wins(self):
        self.p.set_game(True)
        for _ in range(10):
            self.p.add("agent", -100)
            self.p.restart()
        self.p.restart()           # no new round once there is a grand winner
        g = self.p.status()["game"]
        self.assertEqual(g["wins"]["user"], 10)
        self.assertEqual(g["grand"], "user")
        self.p.reset_all()
        self.assertEqual(self.p.status()["game"]["wins"]["user"], 0)

    def test_nothing_counts_when_the_game_is_off(self):
        self.assertIsNone(self.p.gift_in("je te donne 20 points"))
        self.assertEqual(self.p.status()["game"], {"on": False, "wins": {"user": 0, "agent": 0}})
        self.assertNotIn("JEU", self.p.note())

    def test_kept_across_a_restart_and_the_aim_is_to_win(self):
        self.p.set_game(True)
        self.p.set_style("sec")
        self.assertIn("GAGNER", self.p.note())
        again = persona_lib.Persona(Path(self.tmp.name) / "p.json", clock=lambda: self.now[0])
        self.assertEqual((again.status()["style"], again.status()["game"]["user"]), ("sec", 100))


if __name__ == "__main__":
    unittest.main()


class PersonaCommandTests(unittest.TestCase):
    def test_style_and_game_by_voice_are_parsed_and_read_back(self):
        from aiwa_brain import agent_lib
        cmd = agent_lib.parse_command({"persona": {"style": "vanneur", "game": True, "restart": True}}, set())
        self.assertEqual(cmd["persona"], {"style": "vanneur", "game": True, "restart": True})
        phrase = agent_lib.command_phrase(cmd)
        self.assertIn("vanneur", phrase)
        self.assertIn("course lancée", phrase)
        self.assertIsNone(agent_lib.parse_command({"persona": {"style": "inconnu"}}, set()))


class OpenAiwaTests(unittest.TestCase):
    def test_open_aiwa_or_the_application_or_swipe_opens_the_home(self):
        from aiwa_brain import agent_lib
        for word in ("aiwa", "l'application", "swipe", "accueil"):
            self.assertEqual(agent_lib.parse_command({"open": word}, set())["open"], "home", word)
        self.assertEqual(agent_lib.parse_command({"open": "apps"}, set())["open"], "files_app")


class StaleAgentTests(unittest.TestCase):
    def test_what_nobody_answered_is_dropped_so_the_widget_does_not_stay_red(self):
        import time
        from aiwa_brain import agent, state
        now = time.time()
        with state.agent_lock:
            saved = dict(state.agent)
            state.agent.update(say={"id": "s1", "text": "bon j'ouvre", "ts": int(now - 400), "spoken": False}, command={"id": "c1", "ts": int(now - 1000), "items": {"open": "home"}}, proposal=None)
        try:
            agent.expire(now)
            with state.agent_lock:
                self.assertTrue(state.agent["say"]["spoken"])
                self.assertIsNone(state.agent["command"])
        finally:
            with state.agent_lock:
                state.agent.clear()
                state.agent.update(saved)


class OpenIntentTests(unittest.TestCase):
    def test_a_plain_order_to_open_is_understood_without_the_model(self):
        from aiwa_brain import agent_lib
        self.assertEqual(agent_lib.parse_command({"open": agent_lib.open_intent("ouvre l'application aiwa")}, set())["open"], "home")
        self.assertEqual(agent_lib.parse_command({"open": agent_lib.open_intent("montre-moi mes vidéos")}, set())["open"], "files_video")
        self.assertIsNone(agent_lib.open_intent("la page est belle"))
        self.assertIsNone(agent_lib.open_intent("je veux ouvrir le wallet"))

    def test_a_reply_that_only_says_it_is_open_gets_the_command_and_it_needs_no_question(self):
        from unittest import mock
        from aiwa_brain import agent, state
        with state.agent_lock:
            saved = dict(state.agent)
        try:
            with mock.patch.object(agent, "point", return_value=("", "")), mock.patch.object(agent, "_model", return_value='{"say": "Voilà, c\'est ouvert."}'):
                agent._turn("ouvre l'application aiwa", False)
            with state.agent_lock:
                command = state.agent["command"]
            self.assertEqual(command["items"]["open"], "home")
            self.assertTrue(command.get("auto"))
        finally:
            with state.agent_lock:
                state.agent.clear()
                state.agent.update(saved)


class OpenWithoutTheModelTests(unittest.TestCase):
    def test_an_order_to_open_never_waits_for_the_model(self):
        import time
        from unittest import mock
        from aiwa_brain import agent, state
        with state.agent_lock:
            saved = dict(state.agent)
            state.agent.update(busy=False, command=None, say=None)
        try:
            with mock.patch.object(agent, "_model", side_effect=AssertionError("the model must not be asked")):
                self.assertTrue(agent.converse(spoken="ouvre l'application aiwa")["ok"])
                for _ in range(50):
                    with state.agent_lock:
                        if state.agent["command"] and not state.agent["busy"]:
                            break
                    time.sleep(0.05)
            with state.agent_lock:
                command, say = state.agent["command"], state.agent["say"]
            self.assertEqual(command["items"]["open"], "home")
            self.assertTrue(command["auto"])
            self.assertIn("J'ouvre", say["text"])
        finally:
            with state.agent_lock:
                state.agent.clear()
                state.agent.update(saved)


class RealCaseTests(unittest.TestCase):
    """The journal of the phone: « ouvre l'accueil » went to the model (42 s) which answered with a change of repository and session to confirm."""

    def test_l_accueil_is_understood_and_a_switch_nobody_asked_for_is_dropped(self):
        import json
        from unittest import mock
        from aiwa_brain import agent, agent_lib, state
        self.assertEqual(agent_lib.open_intent("ouvre l'accueil"), "accueil")
        reply = {"say": "Bon, j'ouvre l'accueil.", "do": {"repo": "theodoreyong9/Aiwa_app", "session": "session_01XnZ", "open": "accueil"}}
        self.assertEqual(agent_lib.guard_do("ouvre l'accueil", reply["do"]), {"open": "accueil"})
        self.assertIn("session", agent_lib.guard_do("passe sur la session de l'app", reply["do"]))
        with state.agent_lock:
            saved = dict(state.agent)
            state.agent.update(busy=False, command=None, say=None)
        try:
            with mock.patch.object(agent, "point", return_value=("", "")), mock.patch.object(agent, "_model", return_value=json.dumps(reply)):
                agent._turn("dis donc, affiche-moi l'accueil", False)
            with state.agent_lock:
                command = state.agent["command"]
            self.assertEqual(sorted(command["items"]), ["open"])
            self.assertTrue(command["auto"])
        finally:
            with state.agent_lock:
                state.agent.clear()
                state.agent.update(saved)
