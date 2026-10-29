"""The super agent: a turn through a stand-in for Claude, what waits for the phone, confirmation, and what a scenario's double may do at once."""
import json
import unittest
import unittest.mock

from aiwa_brain import agent, config, files, sessions, state, repos


def fresh():
    config.CLOUD_STORE.write_text("[]", encoding="utf-8")
    config.REPOS_STORE.write_text("[]", encoding="utf-8")
    with state.lock:
        state.current_cloud = state.last_cloud = state.current_repo = None
        state.cloud_busy = False
    with state.agent_lock:
        state.agent.update(decisions=[], sig=None, last=0.0, say=None, proposal=None, command=None, last_sent=[], busy=False, error=None)
        state.agent_chat.clear()
    agent._cache.clear()
    files.forget()


def quiet():
    """The network is out of the tests."""
    for name, value in (("aiwa_brain.github.newest_commit_time", 0), ("aiwa_brain.github.latest_run", None), ("aiwa_brain.github.owner_repos", []), ("aiwa_brain.github.my_repos", []),
                        ("aiwa_brain.github.checkout_owner", None), ("aiwa_brain.github.releases", [])):
        patch = unittest.mock.patch(name, return_value=value)
        patch.start()
    return unittest.mock.patch.stopall


class Turn(unittest.TestCase):
    def setUp(self):
        fresh()
        self.addCleanup(quiet())
        sessions.save_cloud_session("session_A1", "Site", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        repos.remember("me/app")

    def run_turn(self, reply, spoken="fais une vidéo pour mon app"):
        asked = []

        def model(system, history, user):
            asked.append((system, user))
            return reply
        with unittest.mock.patch.object(agent, "_model", side_effect=model):
            self.assertTrue(agent.converse(spoken=spoken)["ok"])
            for thread in __import__("threading").enumerate():
                if thread.name != "MainThread" and thread.daemon:
                    thread.join(5)
        return asked

    def test_the_point_is_given_with_the_words_and_the_reply_waits_for_the_phone(self):
        reply = json.dumps({"say": "Je lance la vidéo sur ton app.", "send": [{"repo": "me/app", "message": "Fais une vidéo pour mon app"}]})
        asked = self.run_turn(reply)
        system, user = asked[0]
        self.assertIn("omniscient", system)
        for word in ("me/app", "session_A1", "fais une vidéo pour mon app"):
            self.assertIn(word, user)
        snap = agent.snapshot()
        self.assertEqual(snap["say"]["text"], "Je lance la vidéo sur ton app.")
        self.assertIn("J'envoie à la session du dépôt me/app", snap["proposal"]["read_back"])
        self.assertFalse(snap["busy"])

    def test_nothing_leaves_before_the_person_confirms_then_the_message_goes_to_the_session_of_the_repository(self):
        self.run_turn(json.dumps({"say": "ok", "send": [{"repo": "me/app", "message": "Fais une vidéo"}]}))
        with unittest.mock.patch.object(sessions, "cloud_send", return_value={"ok": True, "session_id": "session_A1"}) as send:
            send.assert_not_called()
            proposal = agent.snapshot()["proposal"]
            result = agent.confirm(proposal["id"])
        send.assert_called_once_with("Fais une vidéo", session=None, repo="me/app")
        self.assertEqual(result, {"ok": True, "sent": ["session_A1"]})
        self.assertIsNone(agent.snapshot()["proposal"])
        self.assertFalse(agent.confirm(proposal["id"])["ok"], "a confirmation is used once")

    def test_a_cancelled_proposal_is_remembered_as_a_decision(self):
        self.run_turn(json.dumps({"send": [{"session": "session_A1", "message": "x"}]}))
        agent.cancel(agent.snapshot()["proposal"]["id"])
        self.assertIsNone(agent.snapshot()["proposal"])
        self.assertIn("ANNULÉE", state.agent["decisions"][-1])

    def test_settings_are_read_back_then_applied_by_the_brain_and_the_screen_is_left_to_the_phone(self):
        self.run_turn(json.dumps({"say": "Je te montre.", "do": {"repo": "me/app", "open": "vidéos"}}), spoken="montre-moi mes vidéos")
        command = agent.snapshot()["command"]
        self.assertEqual((command["open"], command["read_back"]), ("files_video", "J'applique : dépôt me/app, ouvrir les vidéos."))
        out = agent.apply_command(command["id"])
        self.assertEqual(out, {"ok": True, "open": "files_video", "cast": None})
        self.assertEqual((state.current_repo, state.current_cloud), ("me/app", "session_A1"))
        self.assertIsNone(agent.snapshot()["command"])

    def test_a_turn_with_no_model_says_so_and_does_not_stay_busy(self):
        self.run_turn(None)
        snap = agent.snapshot()
        self.assertIn("n'a pas répondu", snap["error"])
        self.assertFalse(snap["busy"])

    def test_the_point_of_a_report_reads_the_workflows(self):
        sessions.save_cloud_session("session_B2", "Autre", None, repo="me/other", work="aiwa/2", base="main", direct=True)
        with unittest.mock.patch("aiwa_brain.github.latest_run", return_value={"state": "failure", "url": "u", "detail": "d"}):
            text, _ = agent.point(report=True)
        self.assertIn("Workflows en échec : me/app, me/other", text)
        self.assertIn("workflow EN ÉCHEC", text)

    def test_stop_forgets_what_waits(self):
        self.run_turn(json.dumps({"send": [{"session": "session_A1", "message": "x"}], "do": {"open": "voir"}}))
        self.assertEqual(agent.stop()["told"], 0)
        snap = agent.snapshot()
        self.assertIsNone(snap["proposal"])
        self.assertIsNone(snap["command"])


class Masters(unittest.TestCase):
    """A scenario's double or the live mode acts at once: the person launched it."""

    def setUp(self):
        fresh()
        self.addCleanup(quiet())
        sessions.save_cloud_session("session_A1", "Site", None, repo="me/app", work="aiwa/1", base="main", direct=True)

    def test_messages_go_at_once_and_the_repository_is_changed_without_a_question(self):
        sent = []
        done = __import__("threading").Event()

        def deliver(message, session=None, repo=None):
            sent.append((message, session, repo))
            done.set()
            return {"ok": True, "session_id": "session_A1"}
        with unittest.mock.patch.object(sessions, "cloud_send", side_effect=deliver):
            screen = agent.act([{"repo": "me/app", "message": "fais la lettre"}], {"repo": "me/app", "open": "documents"})
            self.assertTrue(done.wait(5))
        self.assertEqual(sent, [("fais la lettre", None, "me/app")])
        self.assertTrue(screen)
        self.assertEqual(state.current_repo, "me/app")
        command = agent.snapshot()["command"]
        self.assertTrue(command["auto"])
        self.assertEqual(command["open"], "files_docs")

    def test_nothing_to_do_is_nothing(self):
        self.assertFalse(agent.act([], {}))
        self.assertFalse(agent.act([{"session": "session_NOPE", "message": "x"}], None))


if __name__ == "__main__":
    unittest.main()
