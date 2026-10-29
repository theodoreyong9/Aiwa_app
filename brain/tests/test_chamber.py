"""The chamber's routes: one at a time, Create on both sides, an offer kept for the person, the agent that speaks is the normal one."""
import json
import time
import unittest
import unittest.mock
from unittest import mock

from aiwa_brain import chamber, state


def reset():
    with state.chamber_lock:
        state.chamber.update(active=False, peer=None, name=None, lines=[])
        state.chamber_offers.clear()
    with state.agent_lock:
        state.agent.update(say=None, proposal=None, command=None, busy=False)
    state.match_cache.clear()


def post(path, **body):
    return chamber.chamber_api(path, json.dumps(body))


class Routes(unittest.TestCase):
    def setUp(self):
        reset()
        self.addCleanup(reset)

    def test_one_chamber_at_a_time(self):
        self.assertTrue(post("/api/chamber/active", on=True, peer="anna/profil", name="Anna")["active"])
        busy = post("/api/chamber/active", on=True, peer="luc/profil", name="Luc")
        self.assertEqual((busy["ok"], busy.get("busy")), (False, True))
        self.assertTrue(post("/api/chamber/active", on=True, peer="anna/profil")["ok"], "the same room again is fine")
        self.assertFalse(post("/api/chamber/active", on=True, peer="pas un depot")["ok"])
        self.assertFalse(post("/api/chamber/active", on=False)["active"])

    def test_words_only_without_create_and_the_offer_is_kept_with_it(self):
        post("/api/chamber/active", on=True, peer="anna/profil", name="Anna")
        attach = {"kind": "video", "title": "Ma vidéo", "url": "https://github.com/anna/app/releases/download/video-a/v.mp4"}
        self.assertFalse(post("/api/chamber/deliver", peer="anna/profil", kind="proposal", text="Regarde", attach=attach, danger=False)["ok"])
        with unittest.mock.patch("aiwa_brain.agent.converse") as turn:
            self.assertTrue(post("/api/chamber/deliver", peer="anna/profil", kind="message", text="Salut de son agent", danger=True)["ok"])
            turn.assert_called_once()
            self.assertIn("Anna", turn.call_args.kwargs["spoken"])
        self.assertTrue(post("/api/chamber/deliver", peer="anna/profil", kind="proposal", text="Regarde ma vidéo", attach=attach, danger=True)["ok"])
        view = post("/api/chamber")
        offer = view["offers"][0]
        self.assertEqual((offer["from"], offer["attach"]["kind"]), ("Anna", "video"))
        self.assertIn("Ma vidéo", state.agent["say"]["text"], "the person is told by voice")
        self.assertEqual(post("/api/chamber/offer", id=offer["id"], do="open")["offers"], [])
        self.assertFalse(post("/api/chamber/deliver", peer="luc/profil", kind="message", text="x", danger=True)["ok"], "not the room of this person")

    def test_the_normal_super_agent_speaks_with_the_point_and_the_room_note(self):
        post("/api/chamber/active", on=True, peer="anna/profil", name="Anna")
        seen = {}

        def ask(system, messages, max_tokens=0):
            seen["system"], seen["messages"] = system, messages
            return json.dumps({"say": "Bonjour Anna, je travaille sur une app."})
        with unittest.mock.patch.object(state.llm, "ask", side_effect=ask), unittest.mock.patch.object(type(state.llm), "state", new_callable=unittest.mock.PropertyMock, return_value="ready"), \
                unittest.mock.patch("aiwa_brain.agent.point", return_value=("POINT-DE-TEST", "sig")):
            out = post("/api/chamber/turn", peer="anna/profil", me="Jean", danger=False, incoming={"text": "Salut, tu fais quoi ?"}, peer_note="cherche un associé")
        self.assertEqual(out["say"], "Bonjour Anna, je travaille sur une app.")
        for word in ("omniscient", "MODE CHAMBRE", "POINT-DE-TEST", "PRIVÉ", "cherche un associé"):
            self.assertIn(word, seen["system"])
        self.assertEqual(seen["messages"][-1]["content"], "Salut, tu fais quoi ?")
        self.assertEqual([line["who"] for line in post("/api/chamber")["lines"]], ["them", "me"])

    def test_no_key_no_voice_in_the_chamber(self):
        post("/api/chamber/active", on=True, peer="anna/profil", name="Anna")
        with unittest.mock.patch.object(type(state.llm), "state", new_callable=unittest.mock.PropertyMock, return_value="none"):
            self.assertIn("clé", post("/api/chamber/turn", peer="anna/profil", me="Jean")["error"])

    def test_the_description_is_kept_and_the_score_needs_the_key(self):
        self.assertEqual(post("/api/chamber/note", text="je cherche un associé")["text"], "je cherche un associé")
        with unittest.mock.patch.object(type(state.llm), "state", new_callable=unittest.mock.PropertyMock, return_value="none"):
            self.assertIn("clé", post("/api/match", repo="anna/profil")["error"])
        self.assertFalse(post("/api/match", repo="pas un depot")["ok"])


if __name__ == "__main__":
    unittest.main()


class RankingTest(unittest.TestCase):
    def setUp(self):
        self.chamber = chamber
        self.patches = [mock.patch.dict(chamber._rank, {"queue": [], "scores": {}, "total": 0, "running": False}), mock.patch("aiwa_brain.chamber.profile_lib.repo", return_value="me/me")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_notes_by_groups_and_ranks_the_known(self):
        marks = {"a/a": {"pro": 80, "perso": 70}, "b/b": {"pro": 20, "perso": 30}, "c/c": {"pro": 90, "perso": 90}, "d/d": {"ok": False}}
        with mock.patch("aiwa_brain.chamber._match", side_effect=lambda r: {"ok": True, **marks[r]} if "pro" in marks[r] else {"ok": False}):
            self.assertEqual(self.chamber._rank_start(["a/a", "b/b", "c/c", "d/d", "me/me", "bad"])["queued"], 4)
            for _ in range(100):
                if not self.chamber._rank_view()["running"]:
                    break
                time.sleep(0.05)
        view = self.chamber._rank_view()
        self.assertEqual([i["repo"] for i in view["items"]], ["c/c", "a/a", "b/b"])
        self.assertEqual((view["done"], view["total"]), (3, 4))
