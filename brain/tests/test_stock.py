"""The stock-video banks with the person's own keys: a search with a stand-in of the services, the keys kept and never given back, the downloads limited to the two banks."""
import json
import tempfile
import unittest
from pathlib import Path

from aiwa_brain import stock_lib

PEXELS = {"videos": [{"id": 777, "url": "https://www.pexels.com/video/a-man-on-a-couch-777/", "image": "https://images.pexels.com/x.jpg", "duration": 12, "user": {"name": "Jane Doe"},
          "video_files": [{"link": "https://videos.pexels.com/a-4k.mp4", "width": 3840, "height": 2160, "file_type": "video/mp4"},
                          {"link": "https://videos.pexels.com/a-hd.mp4", "width": 1280, "height": 720, "file_type": "video/mp4"},
                          {"link": "https://videos.pexels.com/a-sd.mp4", "width": 640, "height": 360, "file_type": "video/mp4"}]}]}
PIXABAY = {"hits": [{"id": 5, "pageURL": "https://pixabay.com/videos/x-5/", "tags": "man, sofa, home", "duration": 9, "user": "somebody",
           "videos": {"large": {"url": "https://cdn.pixabay.com/l.mp4", "width": 1920, "height": 1080}, "medium": {"url": "https://cdn.pixabay.com/m.mp4", "width": 1280, "height": 720}}}]}


class StockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []

        def transport(url, headers):
            self.calls.append((url, headers))
            if "pexels" in url:
                return (401, {}) if headers.get("Authorization") == "bad" * 6 else (200, PEXELS)
            return 200, PIXABAY
        self.stock = stock_lib.Stock(home=Path(self.tmp.name), transport=transport)

    def test_a_search_needs_the_persons_key_and_the_key_is_never_given_back(self):
        with self.assertRaises(stock_lib.StockError):
            self.stock.search("homme canapé", "pexels")
        self.assertFalse(self.stock.save_key("pexels", "x!")["ok"])
        self.assertTrue(self.stock.save_key("pexels", "abcdefghij0123456789")["ok"])
        self.assertEqual(self.stock.status(), {"pexels": True, "pixabay": False})
        self.assertNotIn("abcdefghij", json.dumps(self.stock.status()))
        self.assertEqual((self.stock._key_file("pexels").stat().st_mode & 0o777), 0o600)

    def test_pexels_gives_the_hd_file_and_the_licence_and_the_key_goes_in_the_header(self):
        self.stock.save_key("pexels", "abcdefghij0123456789")
        found = self.stock.search("a man on a couch", "pexels", portrait=True)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["link"], "https://videos.pexels.com/a-hd.mp4", "the widest that does not pass 1280, never the 4K")
        self.assertEqual(found[0]["author"], "Jane Doe")
        self.assertIn("Pexels", found[0]["licence"])
        self.assertEqual(self.calls[0][1]["Authorization"], "abcdefghij0123456789")
        self.assertIn("orientation=portrait", self.calls[0][0])

    def test_pixabay_is_read_too(self):
        self.stock.save_key("pixabay", "0123456789abcdef0123")
        found = self.stock.search("man sofa", "pixabay")
        self.assertEqual(found[0]["id"], "pixabay-5")
        self.assertEqual(found[0]["link"], "https://cdn.pixabay.com/m.mp4")
        self.assertIn("key=0123456789abcdef0123", self.calls[0][0])

    def test_a_refused_key_is_said_and_a_download_only_comes_from_the_two_banks(self):
        self.stock.save_key("pexels", "badbadbadbadbadbad")
        with self.assertRaises(stock_lib.StockError) as ctx:
            self.stock.search("x", "pexels")
        self.assertIn("refusée", str(ctx.exception))
        self.assertFalse(self.stock.download({"id": "x", "link": "https://evil.example/a.mp4"})["ok"])
        self.assertFalse(self.stock.download({"id": "x", "link": "http://videos.pexels.com/a.mp4"})["ok"], "https only")


if __name__ == "__main__":
    unittest.main()
