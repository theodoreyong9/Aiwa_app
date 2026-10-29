"""The brain's routes, over a real socket, with nothing on the network."""
import json
import threading
import unittest
import unittest.mock
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from aiwa_brain import config, files, server, sessions, state


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.http.server_address[1]
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()

    def setUp(self):
        config.CLOUD_STORE.write_text("[]", encoding="utf-8")
        files.forget()
        with state.lock:
            state.current_cloud = state.last_cloud = state.current_repo = None
        for name in ("github.owner_repos", "github.my_repos"):
            patch = unittest.mock.patch("aiwa_brain." + name, return_value=[])
            patch.start()
            self.addCleanup(patch.stop)

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=10) as reply:
            return reply.status, reply.headers.get("Content-Type"), reply.read()

    def post(self, path, body=""):
        data = body if isinstance(body, str) else json.dumps(body)
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data.encode(), method="POST")
        with urllib.request.urlopen(request, timeout=10) as reply:
            return json.loads(reply.read())

    def test_the_status_holds_what_the_widget_shows(self):
        _code, _type, raw = self.get("/api/status")
        status = json.loads(raw)
        for key in ("version", "sending", "repo", "cloud_session", "agent", "ask", "chamber", "llm", "claude_login", "relay_cloud", "github_token", "attachments", "cast"):
            self.assertIn(key, status)
        self.assertEqual(status["version"], config.BACKEND_VERSION)
        self.assertEqual(status["agent"]["busy"], False)

    def test_an_unknown_route_is_a_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get("/api/boucles")
        self.assertEqual(caught.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/api/loops/create", {})
        self.assertEqual(caught.exception.code, 404)

    def test_choosing_a_repository_selects_its_session(self):
        sessions.save_cloud_session("session_AAA", "App", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        out = self.post("/api/repo", "https://github.com/me/app")
        self.assertEqual((out["accepted"], out["repo"], out["cloud_session"]), (True, "me/app", "session_AAA"))
        self.assertFalse(self.post("/api/repo", "pas un depot")["accepted"])
        status = json.loads(self.get("/api/status")[2])
        self.assertEqual((status["repo"], status["cloud_session"]), ("me/app", "session_AAA"))

    def test_choosing_a_repository_without_session_makes_one(self):
        out = self.post("/api/repo", "https://github.com/me/fresh")
        self.assertEqual((out["accepted"], out["cloud_session"], out["creating"]), (True, None, True))
        self.assertTrue(self.post("/api/session/new", "me/fresh")["accepted"])
        self.assertFalse(self.post("/api/session/new", "pas un depot")["accepted"])

    def test_selecting_a_session_takes_its_repository(self):
        sessions.save_cloud_session("session_AAA", "App", None, repo="me/app", work="aiwa/1", base="main", direct=True)
        self.assertTrue(self.post("/api/cloud/select", "session_AAA")["accepted"])
        self.assertEqual(state.current_repo, "me/app")
        self.assertFalse(self.post("/api/cloud/select", "n'importe quoi")["accepted"])
        self.assertTrue(self.post("/api/cloud/select", "new")["accepted"])
        self.assertIsNone(state.current_cloud)

    def test_the_files_come_per_kind_and_a_page_comes_as_html(self):
        release = [{"id": 1, "tag": "page-a", "name": "Ma page", "published": 5, "page": "p", "assets": [{"id": 1, "name": "a.html", "size": 3, "url": "https://x/a.html"}]}]
        with unittest.mock.patch("aiwa_brain.github.releases", return_value=release), unittest.mock.patch("aiwa_brain.github.fetch", return_value=b"<h1>A</h1>"):
            listing = json.loads(self.get("/api/files?repo=me/app")[2])
            self.assertEqual(listing["items"]["page"][0]["title"], "Ma page")
            code, content_type, body = self.get("/api/files/page?repo=me/app&tag=page-a")
            self.assertEqual((code, body), (200, b"<h1>A</h1>"))
            self.assertIn("text/html", content_type)
            share = self.post("/api/files/share", {"repo": "me/app", "tag": "page-a"})
            self.assertEqual((share["ok"], share["url"]), (True, "https://x/a.html"))

    def test_the_agent_routes_exist_and_a_bad_one_is_a_404(self):
        self.assertTrue(self.post("/api/agent/stop")["ok"])
        self.assertTrue(self.post("/api/agent/cancel", {"id": "x"})["ok"])
        self.assertFalse(self.post("/api/agent/confirm", {"id": "x"})["ok"])
        with self.assertRaises(urllib.error.HTTPError):
            self.post("/api/agent/create", {})

    def test_the_ceiling_and_the_token_are_settings(self):
        self.assertEqual(self.post("/api/llm/key", {"cap": 50000}), {"ok": True, "cap": 50000})
        self.assertFalse(self.post("/api/llm/key", {"key": "pas une clé"})["ok"])
        self.assertFalse(self.post("/api/github/token", {"token": "trop court"})["ok"])
        token = "ghp_" + "a" * 36
        with unittest.mock.patch("aiwa_brain.github.api", return_value={"login": "me"}):
            out = self.post("/api/github/token", {"token": token})
        self.assertEqual((out["github_token"], out["user"]), (True, "me"))
        self.assertFalse(self.post("/api/github/token", {"clear": True})["github_token"])

    def test_push_mode_is_an_option_and_the_model_is_checked(self):
        self.assertTrue(self.post("/api/options", {"push_main": False})["accepted"])
        self.assertFalse(state.push_main)
        self.post("/api/options", {"push_main": True})
        self.assertFalse(self.post("/api/model", "mauvais modèle !")["accepted"])
        self.assertTrue(self.post("/api/effort", "high")["accepted"])
        self.assertFalse(self.post("/api/effort", "turbo")["accepted"])

    def test_scenarios_and_chamber_answer(self):
        self.assertTrue(json.loads(self.get("/api/scenarios")[2])["scenarios"])
        self.assertFalse(json.loads(self.get("/api/chamber")[2])["active"])
        self.assertTrue(self.post("/api/chamber/active", {"on": True, "peer": "anna/profil", "name": "Anna"})["active"])
        self.assertFalse(self.post("/api/chamber/active", {"on": False})["active"])


if __name__ == "__main__":
    unittest.main()
