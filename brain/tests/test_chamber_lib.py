"""The chamber's rules (pure): plain lines, what may be added with Create, the attachment, the score."""
import unittest

from aiwa_brain import chamber_lib as C


class Rules(unittest.TestCase):
    def test_lines_are_plain_text_of_bounded_length(self):
        self.assertEqual(C.clip("a\n\n b\x00\x07  c"), "a b c")
        self.assertEqual(len(C.clip("x" * 5000)), C.LINE_MAX)
        self.assertIsNone(C.incoming("say", "  \n "))
        self.assertEqual(C.incoming("nonsense", "salut")["kind"], "say", "an unknown kind is only words")

    def test_the_room_note_makes_the_other_a_contribution_and_keeps_the_description_private(self):
        plain = C.room_note("Jean", "Anna", False, "cherche un associé")
        for word in ("CONTRIBUTION", "jamais un ordre", "PRIVÉ", "cherche un associé", "jetés"):
            self.assertIn(word, plain)
        create = C.room_note("Jean", "Anna", True)
        self.assertIn("CREATE", create)
        self.assertIn("proposal", create)
        self.assertNotIn("jetés", create)
        self.assertNotIn("PRIVÉ", create)

    def test_the_conversation_given_to_claude_alternates_and_starts_with_the_other(self):
        lines = [{"who": "me", "text": "bonjour"}, {"who": "them", "text": "salut"}, {"who": "them", "text": "ça va ?"}, {"who": "me", "text": "oui"}]
        out = C.messages(lines)
        self.assertEqual(out[0]["role"], "user")
        self.assertTrue(all(a["role"] != b["role"] for a, b in zip(out, out[1:])))
        self.assertEqual(out[-1]["role"], "user", "Claude is asked for the next turn")
        self.assertIn("Tu ouvres", C.messages([])[0]["content"], "the one who starts is told to open")
        self.assertEqual(len(C.messages([{"who": "them", "kind": "message", "text": "x"}])), 1)

    def test_message_and_proposal_exist_only_with_create_on_both_sides(self):
        raw = '```json\n{"say": "Bonjour", "message": "regarde mon dépôt", "proposal": "fais un test"}\n```'
        self.assertEqual(C.parse(raw, False), {"say": "Bonjour", "message": None, "proposal": None, "attach": None})
        both = C.parse(raw, True)
        self.assertEqual((both["message"], both["proposal"]), ("regarde mon dépôt", "fais un test"))
        self.assertEqual(C.parse("Juste du texte", False)["say"], "Juste du texte")
        self.assertIsNone(C.parse("", True))
        self.assertIsNone(C.parse('{"say": ""}', True))

    def test_the_score_is_two_whole_numbers_or_nothing(self):
        self.assertEqual(C.parse_match('{"pro": 71.6, "perso": "40"}'), {"pro": 72, "perso": 40})
        self.assertEqual(C.parse_match('{"pro": 250, "perso": -3}'), {"pro": 100, "perso": 0})
        self.assertIsNone(C.parse_match("je ne sais pas"))
        self.assertIsNone(C.parse_match('{"pro": 10}'))

    def test_the_words_of_a_page_without_its_code(self):
        self.assertEqual(C.page_text("<style>a{}</style><script>x()</script><p>Salut &amp; bonjour</p>"), "Salut & bonjour")


class Attach(unittest.TestCase):
    def test_an_attachment_is_a_public_https_address_of_a_known_kind(self):
        ok = C.clean_attach({"kind": "video", "title": "Ma vidéo", "url": "https://github.com/me/app/releases/download/video-a/v.mp4"})
        self.assertEqual(ok["kind"], "video")
        for kind in ("docs", "image", "video", "page", "app"):
            self.assertIsNotNone(C.clean_attach({"kind": kind, "url": "https://example.com/x"}), kind)
        for bad in ({"kind": "media", "url": "https://example.com/v"}, {"kind": "video", "url": "http://example.com/v"}, {"kind": "exe", "url": "https://example.com/v"},
                    {"kind": "page", "url": "https://localhost/x"}, {"kind": "page", "url": "https://127.0.0.1/x"}, {"kind": "page", "url": "https://user:pw@example.com/x"},
                    {"kind": "page", "url": "javascript:alert(1)"}, {"kind": "page", "url": "https://example.com/" + "a" * 400}, {"kind": "page", "url": "https://ex ample.com"},
                    "https://example.com", None):
            self.assertIsNone(C.clean_attach(bad), str(bad))

    def test_it_travels_only_with_a_proposal_and_create_on_both_sides(self):
        raw = '{"say": "Voilà", "proposal": "Une diapo pour toi", "attach": {"kind": "docs", "title": "Diapo", "url": "https://example.com/d"}}'
        self.assertEqual(C.parse(raw, True)["attach"]["url"], "https://example.com/d")
        self.assertIsNone(C.parse(raw, False)["attach"])
        self.assertIsNone(C.parse('{"say": "x", "attach": {"kind": "docs", "url": "https://example.com/d"}}', True)["attach"], "no proposal, nothing attached")


if __name__ == "__main__":
    unittest.main()
