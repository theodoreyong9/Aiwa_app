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
