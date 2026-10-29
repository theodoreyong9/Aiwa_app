import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiwa_brain import agent_lib, diagram, live_lib

CODE = "flowchart LR\n  A[Micro] --> B[Agent]\n  B --> C{Schema ?}"


class DiagramTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        for patch in (mock.patch.object(diagram, "FILE", Path(self.dir.name) / "d.json"), mock.patch.dict(diagram._state, {"on": None, "id": 0, "code": ""})):
            patch.start()
            self.addCleanup(patch.stop)

    def test_off_until_asked_and_kept_when_on(self):
        self.assertFalse(diagram.show(CODE))
        self.assertEqual(diagram.snapshot()["code"], "")
        self.assertEqual(diagram.note(live=True), "")
        diagram.set_on(True)
        self.assertTrue(diagram.show("```mermaid\n" + CODE + "\n```"))
        self.assertEqual(diagram.snapshot()["code"], CODE)
        self.assertIn(diagram.MARK, diagram.note(live=True))
        self.assertIn("diagram", diagram.note(live=False))

    def test_stream_opens_with_a_diagram_then_sentences(self):
        s = live_lib.Splitter()
        out = []
        for piece in ["@@DIAG", "RAM\nflowchart LR\n A --> B{x}\n@@E", "ND\nVoici le schéma. Il est ", "simple.\n@@ACTIONS {}"]:
            out += s.feed(piece)
            if s.diagram:
                self.assertEqual(s.take_diagram(), "flowchart LR\n A --> B{x}")      # available in the same step as the first sentence: taken first, then spoken
        last, _ = s.finish()
        self.assertEqual(out + last, ["Voici le schéma.", "Il est simple."])

    def test_no_diagram_changes_nothing(self):
        s = live_lib.Splitter()
        self.assertEqual(s.feed("Bonjour. Ça va"), ["Bonjour."])
        self.assertIsNone(s.take_diagram())

    def test_json_reply_may_carry_a_diagram(self):
        parsed = agent_lib.parse_message({"say": "Voilà", "diagram": CODE}, set())
        self.assertEqual(parsed["diagram"], CODE)
        self.assertEqual(agent_lib.parse_message({"diagram": CODE}, set())["say"], "")


if __name__ == "__main__":
    unittest.main()
