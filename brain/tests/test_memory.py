import tempfile
import unittest
from pathlib import Path

from aiwa_brain import memory


def small(test):
    """The limits are large (thousands of notes): the tests use small ones."""
    test.saved = (memory.MAX_NOTES, memory.CONDENSE_AT, memory.CONDENSE_TAKE, memory.CONDENSE_INTO)
    memory.MAX_NOTES, memory.CONDENSE_AT, memory.CONDENSE_TAKE, memory.CONDENSE_INTO = 100, 60, 30, 6
    test.addCleanup(lambda: setattr(memory, "MAX_NOTES", test.saved[0]) or setattr(memory, "CONDENSE_AT", test.saved[1]) or setattr(memory, "CONDENSE_TAKE", test.saved[2]) or setattr(memory, "CONDENSE_INTO", test.saved[3]))


class MemoryTest(unittest.TestCase):
    def setUp(self):
        memory.FILE = Path(tempfile.mkdtemp()) / "memory.json"
        small(self)

    def test_remember_and_forget(self):
        self.assertEqual(memory.apply("retiens que j'aime le jazz", {"remember": "aime le jazz"}), ["remember"])
        self.assertEqual(memory.recent(), ["aime le jazz"])
        self.assertEqual(memory.apply("oublie le jazz", {"forget": "jazz"}), ["forget"])
        self.assertEqual(memory.notes(), [])

    def test_needs_the_person_to_ask(self):
        self.assertEqual(memory.apply("quel temps fait-il", {"remember": "x"}), [])
        self.assertEqual(memory.apply("[Aiwa — retiens ça", {"remember": "x"}), [])
        self.assertEqual(memory.apply("bonjour", {"forget": "all"}), [])
        self.assertEqual(memory.notes(), [])

    def test_remember_is_an_order_not_a_question(self):
        self.assertEqual(memory.apply("tu te souviens de mon vélo ?", {"remember": "x"}), [])
        self.assertEqual(memory.apply("souviens-toi que mon vélo est bleu", {"remember": "vélo bleu"}), ["remember"])

    def test_only_the_last_are_read_each_time_and_the_others_are_found_on_request(self):
        memory.add("mon vélo est bleu")
        memory.add("ma sœur s'appelle Léa")
        for i in range(8):
            memory.add(f"note sans rapport {i}")
        self.assertEqual(len(memory.recent()), memory.RECENT)
        self.assertNotIn("mon vélo est bleu", memory.recent())
        self.assertEqual(memory.search("quelle heure est-il"), [])      # not a question about what it keeps
        self.assertEqual(memory.search("tu te rappelles de mon vélo ?")[0], "mon vélo est bleu")
        self.assertEqual(memory.search("tu te rappelles de ma soeur ?")[0], "ma sœur s'appelle Léa")      # without the accents too
        self.assertEqual(len(memory.search("qu'est-ce que tu sais sur moi ?")), 10)      # nothing to look for: the newest

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
        small(self)

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
