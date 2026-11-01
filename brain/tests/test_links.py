"""The files ticked for a recipient: remembered per file and per recipient, one way, nothing else touched."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiwa_brain import files, links


class LinksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = mock.patch.object(links, "FILE", Path(self.tmp.name) / "links.json")
        patch.start()
        self.addCleanup(patch.stop)

    def test_files_ticked_for_a_recipient_are_remembered_and_can_be_cleared(self):
        cv = {"repo": "me/app", "tag": "docs-cv", "file": "cv.pdf"}
        self.assertTrue(links.set_links("me/app", "docs-valeur", "valeur.pdf", "a@b.fr", [cv, cv, {"repo": "pas un depot", "tag": "x", "file": "y"}])["ok"])
        self.assertEqual(links.get("me/app", "docs-valeur", "valeur.pdf"), {"a@b.fr": [cv]})
        self.assertEqual(links.get("me/app", "docs-valeur", "autre.pdf"), {})
        links.set_links("me/app", "docs-valeur", "valeur.pdf", "a@b.fr", [])
        self.assertEqual(links.get("me/app", "docs-valeur", "valeur.pdf"), {})

    def test_the_file_is_never_linked_to_itself_and_bad_input_is_refused(self):
        me = {"repo": "me/app", "tag": "docs-valeur", "file": "valeur.pdf"}
        self.assertEqual(links.set_links("me/app", "docs-valeur", "valeur.pdf", "a@b.fr", [me])["count"], 0)
        self.assertFalse(links.set_links("nope", "t", "f", "c", [])["ok"])

    def test_the_card_keeps_the_subject_and_the_text_of_each_recipient(self):
        got = files.parse_cibles({"v": 1, "cibles": [{"kind": "mail", "value": "a@b.fr", "label": "A", "source": "https://b.fr", "subject": "Candidature", "body": "Bonjour,\nje vous écris…"}]})
        self.assertEqual((got[0]["subject"], got[0]["body"].startswith("Bonjour")), ("Candidature", True))
        self.assertEqual(files.parse_cibles({"cibles": [{"kind": "mail", "value": "a@b.fr", "objet": "O", "texte": "T"}]})[0]["subject"], "O")


if __name__ == "__main__":
    unittest.main()
