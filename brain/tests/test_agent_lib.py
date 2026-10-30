"""The super agent's words and its reading of a reply (pure)."""
import json
import unittest

from aiwa_brain import agent_lib as A

KNOWN = {"session_A1", "session_B2"}


class Reading(unittest.TestCase):
    def test_every_word_the_agent_is_taught_to_open_is_understood(self):
        for word in A.OPEN_LIST.split(", "):
            self.assertIn(A.OPEN_KINDS.get(word), A.OPEN_SPOKEN, word)

    def test_open_reaches_every_screen_of_the_widget(self):
        for word, kind in (("Wallet", "wallet"), ("réglages", "settings"), ("mise à jour", "update"), ("écoute", "listen"), ("me rendre visible", "voir_on"), ("caché", "voir_off"),
                           ("proximité", "voir_near"), ("QR code", "voir_qr"), ("favoris", "voir_fav"), ("par lien", "voir_link"), ("vidéos", "files_video"), ("pages", "files_page"),
                           ("scénarios", "scenario"), ("télévision", "cast"), ("chambre", "chambre"), ("rapport", "report")):
            self.assertEqual(A.parse_command({"open": word}, KNOWN), {"open": kind})

    def test_what_was_removed_is_not_openable(self):
        for word in ("boucles", "campagne", "mcp", "projet", "store", "robot"):
            self.assertIsNone(A.parse_command({"open": word}, KNOWN), word)

    def test_a_message_aims_at_a_known_session_or_at_a_repository(self):
        raw = json.dumps({"say": "Je m'en occupe", "send": [{"session": "session_A1", "message": "fais une page"}, {"repo": "me/app", "message": "ajoute la vidéo"},
                                                           {"session": "session_ZZ", "message": "inconnue"}, {"repo": "pas un depot", "message": "x"}, {"repo": "me/app", "message": "doublon"}]})
        parsed = A.parse_message(raw, KNOWN)
        self.assertEqual(parsed["say"], "Je m'en occupe")
        first, more = parsed["proposal"], parsed["proposal"]["more"]
        self.assertEqual((first["session"], first["repo"]), ("session_A1", None))
        self.assertEqual([(m["session"], m["repo"]) for m in more], [(None, "me/app")])

    def test_a_reply_with_nothing_in_it_is_not_one(self):
        self.assertIsNone(A.parse_message("{}", KNOWN))
        self.assertIsNone(A.parse_message("pas du json", KNOWN))
        self.assertIsNone(A.parse_message('{"send": [{"session": "session_A1", "message": ""}]}', KNOWN))

    def test_settings_keep_only_what_is_valid(self):
        self.assertEqual(A.parse_command({"repo": "me/app", "session": "nouvelle"}, KNOWN), {"repo": "me/app", "session": "nouvelle"})
        self.assertEqual(A.parse_command({"session": "session_B2", "repo": "pas valide;"}, KNOWN), {"session": "session_B2"})
        self.assertIsNone(A.parse_command({"session": "session_ZZ"}, KNOWN))
        self.assertEqual(A.parse_command({"cast": {"tv": "Salon", "wait": True}}, KNOWN), {"cast": {"tv": "Salon", "wait": True}})
        self.assertEqual(A.parse_command({"cast": "Salon"}, KNOWN), {"cast": {"tv": "Salon", "wait": False}})
        self.assertNotIn("cast", A.parse_command({"repo": "me/app", "cast": {"tv": "a;b"}}, KNOWN))

    def test_the_phone_reads_back_where_it_goes(self):
        text = A.read_back_all([("à la session Blog", "fais x"), ("à la session du dépôt me/app", "fais y")])
        self.assertIn("2 destinations", text)
        self.assertIn("Blog", text)
        self.assertEqual(A.command_phrase({"repo": "me/app", "open": "files_video"}), "J'applique : dépôt me/app, ouvrir les vidéos.")


class Point(unittest.TestCase):
    SNAP = {
        "pills": {"repo": "me/app", "session": "Blog", "direct": True, "profile": "me/me"},
        "sessions": [{"id": "session_A1", "title": "Blog", "repo": "me/app", "work": "aiwa/1", "commit_age_min": 5, "current": True, "ci": "failure"}],
        "repos": ["me/app", "me/me"], "productions": {"video": {"count": 2, "newest": ["Promo (app)"]}, "docs": {"count": 0, "newest": []}},
        "scenarios": [{"name": "Rapport", "word": "le rapport"}], "chamber": "en cours avec Anna", "asks": [{"session": "Blog", "question": "Quelle couleur ?"}],
    }

    def test_the_point_holds_everything_the_agent_must_know(self):
        text, sig = A.digest(self.SNAP)
        for word in ("me/app", "session_A1", "workflow EN ÉCHEC", "vidéos : 2", "Promo (app)", "le rapport", "Anna", "Quelle couleur ?", "me/me", "dernier commit il y a 5 min"):
            self.assertIn(word, text)
        self.assertNotIn("documents", text.split("Productions")[1], "a kind with nothing is not listed")
        self.assertEqual(sig, A.digest(self.SNAP)[1])

    def test_the_signature_moves_with_real_changes_only(self):
        _t, sig = A.digest(self.SNAP)
        later = json.loads(json.dumps(self.SNAP))
        later["sessions"][0]["commit_age_min"] = 6
        self.assertEqual(A.digest(later)[1], sig, "a passing minute is not news")
        later["productions"]["video"]["count"] = 3
        self.assertNotEqual(A.digest(later)[1], sig)

    def test_the_system_text_makes_it_an_intermediary_that_understands_repositories(self):
        text = A.system("Parle court.")
        for word in ("omniscient", "INTERMÉDIAIRE", "`repo`", "MOT POUR MOT", "DONNÉE", "Parle court."):
            self.assertIn(word, text)
        for gone in ("boucle", "campagne", "connector", "agent externe"):
            self.assertNotIn(gone, text.lower())


if __name__ == "__main__":
    unittest.main()


class ExtraInstructionTest(unittest.TestCase):
    def test_a_standing_instruction_is_read_and_may_be_emptied(self):
        from aiwa_brain import agent_lib
        self.assertEqual(agent_lib.parse_command({"extra": "  Réponds   court. "}, set())["extra"], "Réponds court.")
        self.assertEqual(agent_lib.parse_command({"extra": ""}, set())["extra"], "")
        self.assertEqual(len(agent_lib.parse_command({"extra": "x" * 2000}, set())["extra"]), 600)
        self.assertIsNone(agent_lib.parse_command({"extra": 5}, set()))


class RenameTest(unittest.TestCase):
    def test_a_session_is_renamed_by_voice_the_one_in_use_or_a_known_one(self):
        from aiwa_brain import agent_lib
        self.assertEqual(agent_lib.parse_command({"rename": "Mon site"}, set())["rename"], {"session": "", "title": "Mon site"})
        out = agent_lib.parse_command({"rename": {"session": "session_ABC", "title": "Film"}}, {"session_ABC"})
        self.assertEqual(out["rename"], {"session": "session_ABC", "title": "Film"})
        self.assertIsNone(agent_lib.parse_command({"rename": {"session": "session_ZZZ", "title": "Film"}}, {"session_ABC"}))
        self.assertIsNone(agent_lib.parse_command({"rename": {"title": "<script>"}}, set()))
