import sys
import unittest
from pathlib import Path

from aiwa_brain import warm

FAKE = str(Path(__file__).parent / "fixtures" / "fake_claude.py")


class WarmTest(unittest.TestCase):
    def setUp(self):
        warm.COMMAND = [sys.executable, FAKE]
        warm._kill()

    def tearDown(self):
        warm._kill()

    def test_the_process_is_kept_and_the_short_prompt_is_used_after_the_first(self):
        self.assertEqual(warm.ask("first long", "short"), "n:1 first")
        self.assertEqual(warm.ask("first long", "short"), "n:2 short")      # same process: it counts on

    def test_recycled_after_some_turns_with_the_long_prompt_again(self):
        warm.RECYCLE_AFTER = 2
        try:
            warm.ask("a", "b"); warm.ask("a", "b")
            self.assertEqual(warm.ask("again", "b"), "n:1 again")
        finally:
            warm.RECYCLE_AFTER = 12

    def test_a_crash_or_an_error_gives_none_and_the_next_turn_starts_again(self):
        warm.ask("a", "b")
        self.assertIsNone(warm.ask("a", "CRASH now"))
        self.assertEqual(warm.ask("again", "b"), "n:1 again")
        self.assertIsNone(warm.ask("ERR", "ERR"))

    def test_no_program_means_none(self):
        warm.COMMAND = ["/nonexistent/claude"]
        self.assertIsNone(warm.ask("a", "b"))

