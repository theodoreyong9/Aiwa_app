import unittest
from unittest import mock

from aiwa_brain import scenarios, state

ENTRY = {"id": "session_AAA", "repo": "me/app", "work": "aiwa/1", "title": "App"}


class Immediate:
    """A thread that runs at once, so that the test sees what it did."""
    def __init__(self, target=None, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


class WatchTest(unittest.TestCase):
    def setUp(self):
        state.scenario_watch.clear()
        self.addCleanup(state.scenario_watch.clear)

    def test_a_double_that_sends_and_watches_is_woken_when_the_session_finishes_a_turn(self):
        before = {"sha": "a", "message": "avant", "ci": "success"}
        after = {"sha": "b", "message": "le travail", "ci": "success"}
        woken = []
        with mock.patch.object(scenarios.sessions, "load_all", return_value=[ENTRY]), \
                mock.patch.object(scenarios.live, "look_branch", side_effect=[before, before, after]), \
                mock.patch.object(scenarios, "_scen_sessions", return_value={"critique": {"current": "session_DBL"}}), \
                mock.patch.object(scenarios, "_wake", side_effect=lambda sid, double, text: woken.append((sid, double, text))), \
                mock.patch.object(scenarios.threading, "Thread", Immediate):
            scenarios.watch_start("critique", [{"session": "session_AAA", "message": "fais ça"}])
            scenarios.watch_once()
            self.assertEqual(woken, [])                      # nothing changed since the baseline
            scenarios.watch_once()
        self.assertEqual(len(woken), 1)
        self.assertEqual(woken[0][:2], ("critique", "session_DBL"))
        self.assertIn("le travail", woken[0][2])
        self.assertIn("aiwa/1", woken[0][2])
        self.assertEqual(state.scenario_watch["critique"]["turns"], 1)

    def test_a_workflow_still_running_waits_and_the_stop_ends_the_watch(self):
        base = {"sha": "a", "message": "", "ci": "success"}
        running = {"sha": "b", "message": "", "ci": "running"}
        woken = []
        with mock.patch.object(scenarios.sessions, "load_all", return_value=[ENTRY]), \
                mock.patch.object(scenarios.live, "look_branch", side_effect=[base, running]), \
                mock.patch.object(scenarios, "_scen_sessions", return_value={"critique": {"current": "session_DBL"}}), \
                mock.patch.object(scenarios, "_wake", side_effect=lambda *a: woken.append(a)), \
                mock.patch.object(scenarios, "_scenario_send") as send, \
                mock.patch.object(scenarios.threading, "Thread", Immediate):
            scenarios.watch_start("critique", [{"repo": "me/app", "message": "x"}])
            scenarios.watch_once()
            self.assertEqual(woken, [])                      # the commit is there, the workflow is not finished
            scenarios.watch_stop_all()
        self.assertFalse(state.scenario_watch["critique"]["on"])
        self.assertIn("stop", send.call_args[0][1])

    def test_a_target_that_is_not_one_of_her_sessions_is_not_watched(self):
        with mock.patch.object(scenarios.sessions, "load_all", return_value=[ENTRY]), mock.patch.object(scenarios.live, "look_branch"):
            scenarios.watch_start("critique", [{"session": "session_ZZZ", "message": "x"}])
        self.assertEqual(state.scenario_watch["critique"]["targets"], {})


if __name__ == "__main__":
    unittest.main()
