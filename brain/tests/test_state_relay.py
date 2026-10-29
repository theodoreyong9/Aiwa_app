"""What survives a restart, the questions of Claude, the relay and the silence alert, the cast wish, the ceiling of the key, the self update."""
import json
import time
import unittest
import unittest.mock

from aiwa_brain import asks, cast, config, files, github, llm_lib, relay, scenarios, sessions, state, update


class Saved(unittest.TestCase):
    def test_the_settings_come_back_after_a_restart_and_a_bad_file_is_only_ignored(self):
        with state.lock:
            state.current_repo, state.current_cloud, state.push_main, state.current_effort = "me/app", "session_AAA", False, "high"
        state.save()
        with state.lock:
            state.current_repo = state.current_cloud = None
            state.push_main = True
        state.load()
        self.assertEqual((state.current_repo, state.current_cloud, state.push_main, state.current_effort), ("me/app", "session_AAA", False, "high"))
        topic = state.waiting_topic
        config.STATE_FILE.write_text("{pas du json", encoding="utf-8")
        state.load()
        self.assertIsNone(state.current_repo)
        self.assertRegex(state.waiting_topic, r"aiwa-[a-f0-9]{24}")
        self.assertNotEqual(state.waiting_topic, topic)
        with state.lock:
            state.push_main = True


class Asks(unittest.TestCase):
    def setUp(self):
        with state.lock:
            state.ask_list = []
            state.current_cloud = "session_AAA"

    def test_a_question_is_kept_shown_and_answered_to_its_session(self):
        self.assertTrue(asks.ask_set('{"question": "Quelle couleur ?", "options": ["rouge", "bleu"]}', "e1"))
        self.assertFalse(asks.ask_set('{"question": "Quelle couleur ?"}', "e1"), "the same event is one question")
        self.assertFalse(asks.ask_set("pas une question"))
        shown = asks.snapshot()
        self.assertEqual((shown["question"], shown["options"], shown["count"]), ("Quelle couleur ?", ["rouge", "bleu"], 1))
        with unittest.mock.patch.object(sessions, "cloud_send", return_value={"ok": True}) as send:
            self.assertTrue(asks.answer(json.dumps({"id": "e1", "answer": "bleu"}))["ok"])
        self.assertIn("Quelle couleur ?", send.call_args[0][0])
        self.assertIsNone(asks.snapshot())


class Relay(unittest.TestCase):
    def test_the_relay_address_carries_the_secret_topic(self):
        state.load()
        self.assertTrue(relay.relay_url().endswith("/" + state.waiting_topic))

    def test_a_scenario_word_from_the_relay_is_kept_for_the_phone(self):
        scenarios.said(json.dumps({"scenario": "entretien", "say": "Voilà ma position", "note": "à noter"}))
        out = scenarios.scenario_api("/api/scenarios/said", json.dumps({"id": "entretien"}))
        self.assertEqual(out["says"][0]["say"], "Voilà ma position")

    def test_no_alert_while_the_session_made_a_commit_after_the_message(self):
        sessions.save_cloud_session("session_AAA", "App", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        sent = int(time.time()) - 1200
        with state.lock:
            state.last_message_at, state.cloud_busy, state.current_cloud = sent, False, "session_AAA"
            state.ask_list = []
        state.silence.update(acked_for=0)
        state.waiting.update(since=None, last_ping=None)
        with unittest.mock.patch.object(github, "newest_commit_time", return_value=0):
            self.assertEqual(relay.silence_minutes(), 20, "twenty minutes of nothing")
        with unittest.mock.patch.object(github, "newest_commit_time", return_value=sent + 60):
            self.assertEqual(relay.silence_minutes(), 0)
        relay.clear_waiting()
        with unittest.mock.patch.object(github, "newest_commit_time", return_value=0):
            self.assertEqual(relay.silence_minutes(), 0, "the person looked: it is over")


class CastWish(unittest.TestCase):
    def test_a_video_made_after_the_wish_is_the_one_to_cast(self):
        old = {"id": 1, "tag": "video-a", "name": "Ancienne", "published": 100, "page": "p", "assets": [{"id": 1, "name": "a.mp4", "size": 1, "url": "https://x/a.mp4"}]}
        new = {"id": 2, "tag": "video-b", "name": "Nouvelle", "published": 200, "page": "p", "assets": [{"id": 2, "name": "b.mp4", "size": 1, "url": "https://x/b.mp4"}]}
        files.forget()
        with unittest.mock.patch("aiwa_brain.files.worked_on", return_value=["me/app"]), unittest.mock.patch.object(github, "releases", return_value=[old]):
            cast.cast_register("Salon")
            self.assertIsNone(cast.ready())
        files.forget()
        with unittest.mock.patch("aiwa_brain.files.worked_on", return_value=["me/app"]), unittest.mock.patch.object(github, "releases", return_value=[new, old]):
            self.assertEqual(cast.ready(), {"tv": "Salon", "name": "Nouvelle", "url": "https://x/b.mp4"})
        cast.cast_clear()
        self.assertIsNone(cast.ready())


class Ceiling(unittest.TestCase):
    def test_the_key_stops_at_the_daily_ceiling(self):
        import tempfile
        from pathlib import Path
        tmp = Path(tempfile.mkdtemp())

        class Usage:
            input_tokens, output_tokens = 60, 40

        class Reply:
            stop_reason, usage = "end_turn", Usage()
            content = [type("B", (), {"type": "text", "text": "ok"})()]

        class Client:
            class messages:
                @staticmethod
                def create(**kwargs):
                    return Reply()
        llm = llm_lib.Llm(key_file=tmp / "key", client_factory=lambda key: Client(), usage_file=tmp / "usage.json")
        llm.save_key("sk-ant-" + "a" * 30)
        self.assertEqual(llm.set_cap(150), {"ok": True, "cap": 150})
        self.assertEqual(llm.ask("s", [{"role": "user", "content": "x"}]), "ok")
        self.assertEqual(llm.state, "ready")
        self.assertEqual(llm.ask("s", [{"role": "user", "content": "x"}]), "ok")
        self.assertEqual((llm.usage()["used"], llm.state), (200, "capped"))
        self.assertIsNone(llm.ask("s", [{"role": "user", "content": "x"}]))
        llm.set_cap(0)
        self.assertEqual(llm.state, "ready")
        self.assertFalse(llm.set_cap("beaucoup")["ok"])


class SelfUpdate(unittest.TestCase):
    def test_it_moves_forward_only_a_clean_checkout(self):
        calls = []

        def git(args, **kwargs):
            calls.append(args[5:])
            out = {"status": "", "fetch": "", "rev-parse": "aaa" if len([c for c in calls if c[0] == "rev-parse"]) == 1 else "bbb"}.get(args[5], "")
            return type("R", (), {"stdout": out, "stderr": "", "returncode": 0})()
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        (root / ".git").mkdir()
        self.assertEqual(update.update_once(run=git, root=root), "updated")
        self.assertEqual(update.update_once(run=lambda *a, **k: type("R", (), {"stdout": " M x", "stderr": "", "returncode": 0})(), root=root), "local changes")
        self.assertEqual(update.update_once(run=git, root=Path(tempfile.mkdtemp())), "not a git install")

    def test_the_version_on_disk_is_read_from_the_config(self):
        self.assertEqual(update.disk_version(), config.BACKEND_VERSION)


class Github(unittest.TestCase):
    def test_the_repository_is_read_from_a_link_or_a_name(self):
        for text, repo in (("https://github.com/me/app", "me/app"), ("git@github.com:me/app.git", "me/app"), ("me/app", "me/app"), ("https://github.com/me/app/issues/3", "me/app")):
            self.assertEqual(github.parse_repo(text), repo)
        self.assertIsNone(github.parse_repo("rien du tout"))

    def test_a_release_is_read_with_its_files_and_a_delete_goes_through_the_api(self):
        data = [{"id": 7, "tag_name": "video-a", "name": "A", "published_at": "2026-07-01T10:00:00Z", "html_url": "u", "assets": [{"id": 1, "name": "a.mp4", "size": 4, "browser_download_url": "https://x/a.mp4"}]}, {"name": "sans étiquette"}]
        calls = []

        def api(path, method="GET", body=None, timeout=15):
            calls.append((method, path))
            return data if method == "GET" else None
        with unittest.mock.patch.object(github, "api", side_effect=api):
            found = github.releases("me/app")
            self.assertEqual([(r["tag"], r["assets"][0]["url"]) for r in found], [("video-a", "https://x/a.mp4")])
            self.assertGreater(found[0]["published"], 0)
            github.delete_release("me/app", 7, "video-a")
        self.assertEqual(calls[-2:], [("DELETE", "/repos/me/app/releases/7"), ("DELETE", "/repos/me/app/git/refs/tags/video-a")])

    def test_the_latest_run_is_one_verdict_per_commit(self):
        runs = {"workflow_runs": [
            {"id": 3, "head_sha": "b", "status": "completed", "conclusion": "success", "workflow_id": 1, "name": "ci", "created_at": "2026-07-01T10:00:00Z", "event": "push", "html_url": "u3", "display_title": "t"},
            {"id": 2, "head_sha": "b", "status": "completed", "conclusion": "failure", "workflow_id": 2, "name": "android", "created_at": "2026-07-01T10:00:00Z", "event": "push", "html_url": "u2", "display_title": "t"},
            {"id": 1, "head_sha": "a", "status": "completed", "conclusion": "success", "workflow_id": 2, "name": "android", "created_at": "2026-07-01T09:00:00Z", "event": "push", "html_url": "u1", "display_title": "t"},
        ]}
        with unittest.mock.patch.object(github, "api", return_value=runs):
            verdict = github.latest_run("me/app")
        self.assertEqual((verdict["state"], verdict["url"]), ("failure", "u2"))
        with unittest.mock.patch.object(github, "api", side_effect=github.GithubError("GitHub 500")):
            self.assertIsNone(github.latest_run("me/app"))


if __name__ == "__main__":
    unittest.main()


class ResumeMailboxTest(unittest.TestCase):
    def test_watch_resumes_after_a_restart_only_for_a_recent_message(self):
        from unittest import mock
        from aiwa_brain import relay, state
        entry = {"repo": "me/app", "work": "aiwa/20261029-215133"}
        with mock.patch.object(state, "current_cloud", "session_X"), mock.patch.object(relay.sessions, "entry_of", return_value=entry), mock.patch.object(relay, "mailbox_watch") as watch:
            with mock.patch.object(state, "last_message_at", int(time.time()) - 600):
                self.assertTrue(relay.resume_mailbox())
            watch.assert_called_once_with("me/app", "aiwa/20261029-215133")
            with mock.patch.object(state, "last_message_at", int(time.time()) - 10_000):
                self.assertFalse(relay.resume_mailbox())
            with mock.patch.object(state, "last_message_at", 0):
                self.assertFalse(relay.resume_mailbox())
