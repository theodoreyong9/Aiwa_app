import unittest
import unittest.mock

from aiwa_brain import finder


class FinderTest(unittest.TestCase):
    def test_the_words_of_the_sentence_when_the_model_does_not_answer(self):
        self.assertEqual(finder.fallback_terms("trouve-moi des vidéastes qui font du produit"), ["videastes", "produit"])

    def test_repositories_are_ranked_by_the_number_of_searches_that_found_them(self):
        found = {"video": ["a/p", "b/p"], "film": ["b/p", "c/p"], "clip": ["b/p"]}
        with unittest.mock.patch.object(finder, "terms", return_value=["video", "film", "clip"]), unittest.mock.patch.object(finder, "_search", side_effect=lambda t: found[t]):
            out = finder.find("vidéo")
        self.assertTrue(out["ok"])
        self.assertEqual(out["repos"], ["b/p", "a/p", "c/p"])

    def test_a_refusal_of_github_is_said_and_what_was_found_before_is_kept(self):
        def search(term):
            if term == "second":
                raise RuntimeError("GitHub limite les recherches : réessaie dans une minute.")
            return ["a/p"]
        with unittest.mock.patch.object(finder, "terms", return_value=["first", "second"]), unittest.mock.patch.object(finder, "_search", side_effect=search):
            self.assertEqual(finder.find("x")["repos"], ["a/p"])
        with unittest.mock.patch.object(finder, "terms", return_value=["second"]), unittest.mock.patch.object(finder, "_search", side_effect=search):
            out = finder.find("x")
        self.assertFalse(out["ok"])
        self.assertIn("limite", out["error"])

    def test_no_account_no_search(self):
        with unittest.mock.patch.object(finder.github, "token_value", return_value=None):
            with self.assertRaises(RuntimeError):
                finder._search("video")

    def test_empty_request(self):
        self.assertFalse(finder.find("  ")["ok"])
