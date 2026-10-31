"""Free generated shots on Hugging Face: the token kept and never given back, a shot kept like a stock clip with its card, the quota said as it is, the catalogue following the keys."""
import tempfile
import time
import unittest
from pathlib import Path

from aiwa_brain import hf_lib, stock_lib, video_sources


class HfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stock = stock_lib.Stock(home=Path(self.tmp.name), transport=lambda *a: (200, {}))
        self.video = Path(self.tmp.name) / "v.mp4"
        self.video.write_bytes(b"x")

    def wait(self, hf, job_id):
        for _ in range(50):
            if hf.job(job_id)["state"] != "running":
                break
            time.sleep(0.05)
        return hf.job(job_id)

    def test_token_is_kept_and_not_returned(self):
        self.assertTrue(self.stock.save_key("hf", "hf_abcdefghijklmnopqrstuvwx")["ok"])
        self.assertEqual(self.stock.status(), {"pexels": False, "pixabay": False, "hf": True})
        self.assertFalse(self.stock.save_key("hf", "court")["ok"])

    def test_a_shot_becomes_a_clip_with_a_card(self):
        hf = hf_lib.Hf(self.stock, runner=lambda cfg, p, i, t: str(self.video))
        job = self.wait(hf, hf.start("un chat sur un toit")["id"])
        self.assertEqual(job["state"], "done")
        clip = self.stock.clips()[0]
        self.assertEqual(clip["source"], "hf")
        self.assertIn("IA", clip["licence"])

    def test_quota_is_said(self):
        def boom(*a):
            raise RuntimeError("ZeroGPU quota exceeded")
        hf = hf_lib.Hf(self.stock, runner=boom)
        job = self.wait(hf, hf.start("x")["id"])
        self.assertTrue(job["quota"])
        self.assertIn("quota", job["error"])

    def test_catalogue_follows_the_keys(self):
        self.assertIn("fal.ai", video_sources.line({"hf": True}).split("Il manque")[1])
        self.assertNotIn("fal.ai", video_sources.line({"fal": True, "pexels": True}).split("Il manque")[-1] if "Il manque" in video_sources.line({"fal": True, "pexels": True}) else "")


if __name__ == "__main__":
    unittest.main()


class ShotTests(unittest.TestCase):
    def test_command_with_a_shot_is_read_back_and_unsafe_is_dropped(self):
        from aiwa_brain import agent_lib
        cmd = agent_lib.parse_command({"shot": {"prompt": "un renard dans la neige", "source": "hf"}}, set())
        self.assertEqual(cmd["shot"]["source"], "hf")
        self.assertIn("Hugging Face", agent_lib.command_phrase(cmd))
        self.assertEqual(agent_lib.parse_command({"shot": {"prompt": "x", "source": "bizarre"}}, set())["shot"]["source"], "auto")

    def test_auto_choice_follows_keys_and_the_kind_of_plan(self):
        from unittest import mock
        from aiwa_brain import studio
        with tempfile.TemporaryDirectory() as tmp:
            bank = stock_lib.Stock(home=Path(tmp), transport=lambda *a: (200, {}))
            with mock.patch.object(studio, "stock", bank):
                self.assertEqual(studio.choose("une rue de Paris"), "hf")
                bank.save_key("pexels", "abcdefghijklmnopqrstuvwx")
                self.assertEqual(studio.choose("une rue de Paris"), "stock")
                self.assertEqual(studio.choose("un dragon imaginaire"), "hf")
                self.assertEqual(studio.choose("une rue", "hf"), "hf")


class AutoSaveTests(unittest.TestCase):
    def test_a_made_shot_goes_to_the_repository_by_itself_and_is_told_on_demand(self):
        from unittest import mock
        from aiwa_brain import studio
        with tempfile.TemporaryDirectory() as tmp:
            bank = stock_lib.Stock(home=Path(tmp), transport=lambda *a: (200, {}))
            video = Path(tmp) / "v.mp4"
            video.write_bytes(b"x")
            sent = []
            gen = hf_lib.Hf(bank, runner=lambda cfg, p, i, t: str(video), on_clip=lambda cid: (sent.append(cid), studio.stock_saved.update({cid: {"state": "saved", "error": ""}})))
            with mock.patch.object(studio, "stock", bank), mock.patch.object(studio, "hf", gen):
                shot = studio.shoot("un renard", "hf")
                for _ in range(50):
                    if gen.job(shot["id"])["state"] != "running":
                        break
                    time.sleep(0.05)
                time.sleep(0.1)
                self.assertEqual(sent, ["hf-" + shot["id"]])
                self.assertIn("prêt dans le dépôt", studio.shots_line())
