"""The productions: releases read by their tag, the list per kind, delete and share."""
import unittest
import unittest.mock

from aiwa_brain import files, github

RELEASES = [
    {"id": 3, "tag": "video-promo-20260701", "name": "Vidéo de lancement", "published": 300, "page": "https://github.com/me/app/releases/tag/video-promo-20260701",
     "assets": [{"id": 1, "name": "promo.mp4", "size": 5_000_000, "url": "https://github.com/me/app/releases/download/video-promo-20260701/promo.mp4"}]},
    {"id": 2, "tag": "page-accueil-20260630", "name": "page-accueil-20260630", "published": 200, "page": "p",
     "assets": [{"id": 2, "name": "accueil.html", "size": 3000, "url": "https://github.com/me/app/releases/download/page-accueil-20260630/accueil.html"}]},
    {"id": 1, "tag": "android-latest", "name": "APK", "published": 100, "page": "p", "assets": [{"id": 3, "name": "app.apk", "size": 9, "url": "https://x/app.apk"}]},
]


class Productions(unittest.TestCase):
    def setUp(self):
        files.forget()
        patch = unittest.mock.patch.object(github, "releases", side_effect=lambda repo: [dict(r) for r in RELEASES] if repo == "me/app" else [])
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_tag_says_the_kind(self):
        for tag, kind in (("docs-cv", "docs"), ("image-affiche", "image"), ("video-a", "video"), ("app-b", "app"), ("page-c", "page"), ("Video-D", "video")):
            self.assertEqual(files.kind_of(tag), kind)
        for tag in ("android-latest", "v1.0", "", None, "videos-x"):
            self.assertIsNone(files.kind_of(tag), tag)

    def test_a_repository_lists_its_productions_by_kind_newest_first(self):
        listing = files.listing("me/app")
        self.assertEqual([i["title"] for i in listing["items"]["video"]], ["Vidéo de lancement"])
        page = listing["items"]["page"][0]
        self.assertEqual((page["title"], page["file"]), ("accueil", "accueil.html"), "a release with no name is titled from its file")
        self.assertEqual(listing["items"]["docs"], [])
        self.assertNotIn("android-latest", str(listing), "the APK is not a production")

    def test_all_reads_every_known_repository(self):
        with unittest.mock.patch("aiwa_brain.repos.names", return_value=["me/app", "me/other"]):
            listing = files.listing(None)
        self.assertIsNone(listing["repo"])
        self.assertEqual(len(listing["items"]["video"]), 1)

    def test_an_error_of_one_repository_is_said_and_the_others_still_come(self):
        def fail(repo):
            if repo == "me/bad":
                raise github.GithubError("GitHub 404")
            return [dict(r) for r in RELEASES]
        with unittest.mock.patch.object(github, "releases", side_effect=fail), unittest.mock.patch("aiwa_brain.repos.names", return_value=["me/bad", "me/app"]):
            listing = files.listing(None)
        self.assertIn("me/bad", listing["error"])
        self.assertEqual(len(listing["items"]["video"]), 1)

    def test_delete_needs_the_token_and_removes_the_release(self):
        with unittest.mock.patch.object(github, "token_value", return_value=None):
            self.assertIn("jeton", files.delete("me/app", "video-promo-20260701")["error"])
        with unittest.mock.patch.object(github, "token_value", return_value="x" * 30), unittest.mock.patch.object(github, "delete_release") as gone:
            self.assertEqual(files.delete("me/app", "video-promo-20260701"), {"ok": True})
            gone.assert_called_once_with("me/app", 3, "video-promo-20260701")
        self.assertFalse(files.delete("me/app", "video-nope")["ok"])

    def test_share_gives_the_address_of_the_file(self):
        out = files.share("me/app", "video-promo-20260701")
        self.assertEqual((out["ok"], out["title"], out["kind"]), (True, "Vidéo de lancement", "video"))
        self.assertTrue(out["url"].startswith("https://github.com/me/app/releases/download/"))
        self.assertFalse(files.share("pas un depot", "x")["ok"])

    def test_a_page_is_handed_over_as_html_and_nothing_else_is(self):
        with unittest.mock.patch.object(github, "fetch", return_value=b"<h1>Bonjour</h1>"):
            self.assertEqual(files.page_html("me/app", "page-accueil-20260630"), "<h1>Bonjour</h1>")
            self.assertIsNone(files.page_html("me/app", "video-promo-20260701"))

    def test_the_summary_counts_what_was_read(self):
        files.listing("me/app")
        out = files.summary()
        self.assertEqual(out["video"]["count"], 1)
        self.assertEqual(out["docs"]["count"], 0)
        self.assertIn("Vidéo de lancement (app)", out["video"]["newest"])


if __name__ == "__main__":
    unittest.main()
