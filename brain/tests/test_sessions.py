"""Sessions: one per repository, found or made when the person talks about the repository; messages go the way the person's own would."""
import json
import unittest
import unittest.mock

from aiwa_brain import config, instructions, sessions, state


def fresh():
    config.CLOUD_STORE.write_text("[]", encoding="utf-8")
    with state.lock:
        state.current_cloud = state.last_cloud = state.current_repo = None
        state.cloud_busy = False
        state.push_main = True
    state.attachments.clear()


class Linked(unittest.TestCase):
    def setUp(self):
        fresh()

    def test_the_session_of_a_repository_is_the_newest_one_that_works_on_it(self):
        sessions.save_cloud_session("session_AAA", "Vieille", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        sessions.save_cloud_session("session_BBB", "Autre", None, repo="me/other", work="aiwa/2", base="main", direct=True)
        sessions.save_cloud_session("session_CCC", "Récente", None, repo="me/app", work="aiwa/3", base="main", direct=True)
        self.assertEqual(sessions.session_for_repo("me/app"), "session_CCC")
        self.assertEqual(sessions.session_for_repo("me/other"), "session_BBB")
        self.assertIsNone(sessions.session_for_repo("me/none"))

    def test_talking_about_a_repository_selects_its_session_or_leaves_room_for_a_new_one(self):
        sessions.save_cloud_session("session_AAA", "App", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        self.assertEqual(sessions.focus("me/app"), "session_AAA")
        self.assertEqual((state.current_repo, state.current_cloud), ("me/app", "session_AAA"))
        self.assertIsNone(sessions.focus("me/new"))
        self.assertEqual((state.current_repo, state.current_cloud), ("me/new", None))
        self.assertEqual(json.loads(config.REPOS_STORE.read_text())[0], "me/new", "a repository named is remembered")

    def test_a_message_aimed_at_a_repository_goes_to_its_session_with_the_instructions(self):
        sessions.save_cloud_session("session_AAA", "App", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        sessions.save_cloud_session("session_BBB", "Autre", None, repo="me/other", work="aiwa/2", base="main", direct=True)
        sessions.focus("me/other")
        sent = []
        with unittest.mock.patch.object(sessions, "queue_followup", side_effect=lambda sid, text: sent.append((sid, text)) or {"ok": True, "url": "https://claude.ai/code/" + sid, "error": None}), \
                unittest.mock.patch("aiwa_brain.github.default_branch_or_none", return_value="main"), unittest.mock.patch("aiwa_brain.relay.mailbox_watch"):
            result = sessions.cloud_send("fais une page", repo="me/app")
        self.assertTrue(result["ok"])
        self.assertEqual(result["session_id"], "session_AAA")
        self.assertEqual(sent[0][0], "session_AAA")
        self.assertIn("fais une page", sent[0][1])
        self.assertIn("Dépôt : me/app", sent[0][1])
        self.assertEqual(state.current_cloud, "session_AAA", "the person works there now")

    def test_the_instructions_are_told_once_and_again_only_when_they_change(self):
        text, told = instructions.compose({}, "me/app", "aiwa/1", "main", True)
        for word in ("Dépôt : me/app", "RELEASE", "docs-", "video-", "skills/video/SKILL.md", "skills/release/SKILL.md", "Alerte", "aiwa-ask", "CLAUDE.local.md"):
            self.assertIn(word, text)
        again, _ = instructions.compose({"instr": told}, "me/app", "aiwa/1", "main", True)
        self.assertEqual(again, "")
        changed, _ = instructions.compose({"instr": told}, "me/app", "aiwa/1", "main", False)
        self.assertIn("N'intègre RIEN", changed)
        self.assertNotIn("Dépôt : me/app", changed)

    def test_the_text_is_short_enough_for_a_first_message(self):
        text, _ = instructions.compose({}, "me/app", "aiwa/20260701-120000", "main", True)
        self.assertLess(len(text), 12000)

    def test_nothing_is_sent_while_another_send_runs(self):
        with state.lock:
            state.cloud_busy = True
        self.assertEqual(sessions.cloud_send("x", repo="me/app")["error"], "busy")

    def test_a_new_session_needs_a_repository(self):
        self.assertIn("dépôt", sessions.cloud_send("fais quelque chose")["error"])

    def test_an_imported_session_by_its_link_works_on_the_repository_in_use(self):
        state.current_repo = "me/app"
        with unittest.mock.patch("aiwa_brain.github.default_branch", return_value="main"):
            session, why = sessions.cloud_add("voici https://claude.ai/code/session_ZZZ999")
        self.assertEqual(session, "session_ZZZ999")
        self.assertEqual(sessions.entry_of("session_ZZZ999")["repo"], "me/app")



class MakeSessionTest(unittest.TestCase):
    def test_a_failed_creation_is_kept_and_a_good_one_clears_it(self):
        from unittest import mock
        from aiwa_brain import state
        with mock.patch.object(sessions, "cloud_send", return_value={"ok": False, "error": "claude n'est pas connecté"}):
            sessions.make_session()
        self.assertEqual(state.session_error, "claude n'est pas connecté")
        with mock.patch.object(sessions, "cloud_send", return_value={"ok": False, "error": "busy"}):
            sessions.make_session()
        self.assertEqual(state.session_error, "claude n'est pas connecté", "« busy » is another send, not this creation")
        with mock.patch.object(sessions, "cloud_send", return_value={"ok": True}):
            sessions.make_session()
        self.assertIsNone(state.session_error)

if __name__ == "__main__":
    unittest.main()
