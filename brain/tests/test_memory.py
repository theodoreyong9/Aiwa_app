import tempfile
import unittest
from pathlib import Path

from aiwa_brain import memory


class MemoryTest(unittest.TestCase):
    def setUp(self):
        memory.FILE = Path(tempfile.mkdtemp()) / "memory.json"

    def test_remember_and_forget(self):
        self.assertEqual(memory.apply("retiens que j'aime le jazz", {"remember": "aime le jazz"}), ["remember"])
        self.assertEqual(memory.digest(), ["aime le jazz"])
        self.assertEqual(memory.apply("oublie le jazz", {"forget": "jazz"}), ["forget"])
        self.assertEqual(memory.notes(), [])

    def test_needs_the_person_to_ask(self):
        self.assertEqual(memory.apply("quel temps fait-il", {"remember": "x"}), [])
        self.assertEqual(memory.apply("[Aiwa — retiens ça", {"remember": "x"}), [])
        self.assertEqual(memory.apply("bonjour", {"forget": "all"}), [])
        self.assertEqual(memory.notes(), [])

    def test_no_duplicate_and_caps(self):
        memory.add("a")
        self.assertIsNone(memory.add("A"))
        for i in range(120):
            memory.add(f"n{i}")
        self.assertEqual(len(memory.notes()), memory.MAX_NOTES)
        self.assertEqual(memory.forget("all"), memory.MAX_NOTES)


class CondenseTest(unittest.TestCase):
    def setUp(self):
        memory.FILE = Path(tempfile.mkdtemp()) / "memory.json"

    def test_condense_replaces_the_oldest(self):
        for i in range(memory.CONDENSE_AT):
            memory.add(f"note {i}")
        self.assertEqual(memory.to_condense(), [])
        memory.add("one more")
        old = memory.to_condense()
        self.assertEqual(len(old), memory.CONDENSE_TAKE)
        self.assertTrue(memory.replace(old, ["résumé a", "résumé b"]))
        texts = [n["text"] for n in memory.notes()]
        self.assertEqual(texts[:2], ["résumé a", "résumé b"])
        self.assertEqual(len(texts), memory.CONDENSE_AT + 1 - memory.CONDENSE_TAKE + 2)
        self.assertIn("one more", texts)

    def test_bad_answer_changes_nothing(self):
        for i in range(memory.CONDENSE_AT + 1):
            memory.add(f"n{i}")
        old = memory.to_condense()
        self.assertFalse(memory.replace(old, "nope"))
        self.assertEqual(len(memory.notes()), memory.CONDENSE_AT + 1)


if __name__ == "__main__":
    unittest.main()
