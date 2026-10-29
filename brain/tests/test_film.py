"""The film circuit: the quote, the confirmation, the production scene by scene with a stand-in of fal (nothing leaves the machine), the assembly with the real ffmpeg."""
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from aiwa_brain import film_lib

HAVE_FFMPEG = bool(shutil.which("ffmpeg"))


def make_clip(path, with_audio=True):
    args = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24:duration=1"]
    if with_audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    args += ["-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True)


class FakeFal:
    """Answers like fal's queue: a request gets an id, the status is COMPLETED at once, the result holds a file:// URL of a real clip made here."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.calls = []
        self.fail_on = None
        if HAVE_FFMPEG:        # the CI runner of the Android job has no ffmpeg: the tests that make a film are skipped there
            make_clip(self.folder / "video.mp4", with_audio=False)
            make_clip(self.folder / "mouth.mp4")
        (self.folder / "voice.wav").write_bytes(b"RIFF0000WAVE")

    def __call__(self, method, url, payload=None, key=None):
        self.calls.append((method, url, payload))
        if "openapi.json" in url:
            return 404, {}
        if method == "POST":
            if self.fail_on and self.fail_on in url:
                return 422, {"detail": [{"loc": ["body", "prompt"], "msg": "field required"}]}
            role = "mouth" if "lipsync" in url else "voice" if "f5-tts" in url else "video"
            return 200, {"status_url": f"https://q/status/{role}", "response_url": f"https://q/result/{role}"}
        if "/status/" in url:
            return 200, {"status": "COMPLETED"}
        role = url.rsplit("/", 1)[-1]
        if role == "voice":
            return 200, {"audio_url": {"url": (self.folder / "voice.wav").as_uri()}}
        return 200, {"video": {"url": (self.folder / f"{role}.mp4").as_uri()}}


class FilmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fal = FakeFal(self.tmp.name)
        planner = lambda direction, says, seconds, kind="me": {"scenes": [
            {"situation": "il marche sur une plage", "seconds": 5, "says": ""},
            {"situation": "il regarde la caméra et sourit", "seconds": 5, "says": "Bonjour à tous"},
            {"situation": "il dit un mot que personne n'a écrit", "seconds": 5, "says": "Une phrase inventée"},
        ]}
        self.film = film_lib.Film(home=Path(self.tmp.name) / "home", transport=self.fal, planner=planner, sleep=lambda s: None)
        self.film.save_key("abcd1234:efgh5678abcd1234")
        self.film.save_voice(b"voice-bytes", "m4a")

    def prepare(self, **kw):
        args = dict(direction="un film de moi", says="Bonjour à tous", photos=[b"jpgbytes"], consent=True)
        args.update(kw)
        return self.film.prepare(**args)

    def test_nothing_starts_without_the_key_the_consent_the_photos_or_the_voice(self):
        self.film.clear_key()
        self.assertFalse(self.prepare()["ok"])
        self.film.save_key("abcd1234:efgh5678abcd1234")
        self.assertFalse(self.prepare(consent=False)["ok"])
        self.assertFalse(self.prepare(photos=[])["ok"])
        for old in self.film.home.glob("voice_sample.*"):
            old.unlink()
        self.assertFalse(self.prepare()["ok"], "words need the voice sample")
        self.assertTrue(self.prepare(says="")["ok"], "a film without words does not")
        self.assertEqual(self.fal.calls, [], "nothing was sent to fal")

    def test_only_the_words_she_gave_are_ever_said_and_the_quote_is_computed(self):
        quote = self.prepare()
        scenes = quote["scenes"]
        self.assertEqual(scenes[1]["says"], "Bonjour à tous")
        self.assertEqual(scenes[2]["says"], "", "a phrase she did not give is dropped")
        self.assertAlmostEqual(scenes[0]["price"], 0.56, places=2)           # 5 s of picture
        self.assertAlmostEqual(scenes[1]["price"], 0.56 + 0.35 + 0.0007, places=2)   # picture + mouth + voice
        self.assertAlmostEqual(quote["total"], sum(s["price"] for s in scenes), places=1)
        self.assertEqual(self.fal.calls, [])

    def test_no_production_without_the_confirmation_or_above_the_cap(self):
        job_id = self.prepare()["id"]
        self.assertFalse(self.film.start(job_id, confirmed=False)["ok"])
        self.film.set_cap(1.0)
        refused = self.film.start(job_id, confirmed=True)
        self.assertFalse(refused["ok"])
        self.assertIn("plafond", refused["error"])
        self.assertEqual([c for c in self.fal.calls if c[0] == "POST"], [])

    def wait(self, job_id):
        for _ in range(300):
            view = self.film.get(job_id)
            if view["state"] in ("done", "error"):
                return view
            time.sleep(0.1)
        self.fail("the film never finished")

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg needed")
    def test_the_production_makes_a_film_and_a_new_prompt_redoes_only_the_changed_scene(self):
        job_id = self.prepare()["id"]
        self.assertTrue(self.film.start(job_id, confirmed=True)["ok"])
        view = self.wait(job_id)
        self.assertEqual(view["state"], "done", view["error"])
        film = self.film.home / job_id / view["film"]
        self.assertTrue(film.exists())
        tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=comment", "-of", "csv=p=0", str(film)], capture_output=True, text=True).stdout
        self.assertIn("Généré par IA", tags)
        posts = [c for c in self.fal.calls if c[0] == "POST"]
        self.assertEqual(len(posts), 3 + 1 + 1, "3 pictures, 1 voice, 1 mouth")
        self.assertTrue(all(c[2] for c in posts))
        # the photo and the voice sample travel as data URIs inside the request, never as a key
        self.assertTrue(any("data:image/jpeg;base64," in json.dumps(c[2]) for c in posts))
        self.assertFalse(any("abcd1234" in json.dumps(c[2]) for c in posts))
        # a new prompt for scene 0 only: the others are already made and cost nothing
        self.fal.calls.clear()
        edited = self.film.edit(job_id, 0, situation="il court sur une plage")
        self.assertEqual([s["done"] for s in edited["scenes"]], [False, True, True])
        self.assertAlmostEqual(edited["total"], 0.56, places=2)
        self.film.start(job_id, confirmed=True)
        self.assertEqual(self.wait(job_id)["state"], "done")
        self.assertEqual(len([c for c in self.fal.calls if c[0] == "POST"]), 1)

    def test_a_refusal_of_fal_is_shown_as_it_is(self):
        job_id = self.prepare(says="")["id"]
        self.fal.fail_on = "kling"
        self.film.start(job_id, confirmed=True)
        view = self.wait(job_id)
        self.assertEqual(view["state"], "error")
        self.assertIn("422", view["error"])
        self.assertIn("field required", view["error"])

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg needed")
    def test_a_product_film_has_a_voice_over_and_no_mouth_and_no_clone(self):
        wav = Path(self.tmp.name) / "vo.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=1", str(wav)], check=True)
        self.film.voiceover = lambda text: wav.read_bytes()
        for old in self.film.home.glob("voice_sample.*"):
            old.unlink()        # no voice sample is needed for a product film
        refused = self.film.prepare("la gourde en randonnée", "Bonjour à tous", photos=[b"jpg"], consent=False, kind="product")
        self.assertIn("produit", refused["error"])
        quote = self.film.prepare("la gourde en randonnée", "Bonjour à tous", photos=[b"jpg"], consent=True, kind="product")
        self.assertTrue(quote["ok"], quote)
        self.assertEqual(quote["kind"], "product")
        said = [s for s in quote["scenes"] if s["says"]]
        self.assertTrue(said and all(abs(s["price"] - 0.112 * s["seconds"]) < 0.001 for s in quote["scenes"]), "no mouth, no clone to pay: only the picture")
        self.film.start(quote["id"], confirmed=True)
        view = self.wait(quote["id"])
        self.assertEqual(view["state"], "done", view["error"])
        posts = [c[1] for c in self.fal.calls if c[0] == "POST"]
        self.assertTrue(all("kling" in u for u in posts), "nothing but the picture was asked of fal")
        prompts = [json.dumps(c[2]) for c in self.fal.calls if c[0] == "POST"]
        self.assertTrue(all("strictement identique" in p for p in prompts))
        self.assertEqual(film_lib.Film.films(self.film)[0]["kind"], "product")

    def test_a_film_with_the_person_and_the_product_needs_both_and_sends_both_references(self):
        refused = self.film.prepare("moi avec la gourde", "Bonjour à tous", photos=[b"moi"], consent=True, kind="both")
        self.assertIn("produit", refused["error"])
        quote = self.film.prepare("moi avec la gourde", "Bonjour à tous", photos=[b"moi1", b"moi2"], photos_product=[b"prod1"], consent=True, kind="both")
        self.assertTrue(quote["ok"], quote)
        said = [s for s in quote["scenes"] if s["says"]]
        self.assertTrue(said and said[0]["price"] > 0.112 * said[0]["seconds"], "the mouth and the voice are paid in this mode too")
        if HAVE_FFMPEG:
            self.film.start(quote["id"], confirmed=True)
            view = self.wait(quote["id"])
            self.assertEqual(view["state"], "done", view["error"])
            first = [c[2] for c in self.fal.calls if c[0] == "POST" and "kling" in c[1]][0]
            self.assertEqual(len(first["image_urls"]), 3, "two photos of the person and one of the product, together")
            self.assertIn("strictement identiques", first["prompt"])

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg needed")
    def test_a_swap_is_made_on_the_persons_own_video_and_quoted_by_its_length(self):
        refused = self.film.prepare("", photos=[b"prod"], consent=False, kind="swap")
        self.assertIn("vidéo est à toi", refused["error"])
        refused = self.film.prepare("", photos=[b"moi"], consent=False, kind="swap", swap="person")
        self.assertIn("personne remplacée est d'accord", refused["error"])
        quote = self.film.prepare("la gourde bleue", photos=[b"prod"], consent=True, kind="swap", swap="product")
        self.assertTrue(quote["ok"], quote)
        self.assertEqual(quote["state"], "needs_video")
        self.assertFalse(self.film.start(quote["id"], confirmed=True)["ok"], "no video yet")
        clip = Path(self.tmp.name) / "mine.mp4"
        make_clip(clip)                       # one second
        data = clip.read_bytes()
        view = self.film.set_source(quote["id"], data)
        self.assertTrue(view["ok"], view)
        self.assertEqual(view["state"], "quoted")
        self.assertEqual(view["scenes"][0]["seconds"], 1)
        self.assertAlmostEqual(view["total"], 0.08, places=2)
        self.assertFalse(self.film.set_source("nope", data)["ok"])
        self.film.start(quote["id"], confirmed=True)
        done = self.wait(quote["id"])
        self.assertEqual(done["state"], "done", done["error"])
        sent = [c[2] for c in self.fal.calls if c[0] == "POST" and "pixverse" in c[1]][0]
        self.assertTrue(sent["video_url"].startswith("data:video/mp4;base64,"))
        self.assertTrue(sent["image_url"].startswith("data:image/jpeg;base64,"))

    def test_the_key_is_never_given_back(self):
        status = self.film.status()
        self.assertTrue(status["key"])
        self.assertNotIn("abcd1234", json.dumps(status))
        self.assertEqual((self.film.key_file.stat().st_mode & 0o777), 0o600)
        self.assertFalse(self.film.save_key("pas une clé!")["ok"])


class FilmKeepingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def make(self):
        film = film_lib.Film(home=Path(self.tmp.name), planner=lambda d, s, n, k="me": {"scenes": [{"situation": "une scène", "seconds": 5, "says": ""}, {"situation": "une autre", "seconds": 5, "says": ""}]}, sleep=lambda s: None)
        film.save_key("abcd1234:efgh5678abcd1234")
        return film

    def test_a_film_can_be_retouched_after_the_brain_restarts(self):
        first = self.make()
        quote = first.prepare("un film", photos=[b"jpg"], consent=True)
        again = self.make()          # a new brain: the plan comes back from the disk
        view = again.edit(quote["id"], 0, situation="une scène changée")
        self.assertTrue(view["ok"], view)
        self.assertEqual(view["scenes"][0]["situation"], "une scène changée")

    def test_deleting_the_film_keeps_the_drafts_unless_asked(self):
        film = self.make()
        quote = film.prepare("un film", photos=[b"jpg"], consent=True)
        folder = film.home / quote["id"]
        (folder / "film.mp4").write_bytes(b"x")
        (folder / "scene_abc.mp4").write_bytes(b"y")
        self.assertTrue(film.delete(quote["id"], drafts=False)["ok"])
        self.assertFalse((folder / "film.mp4").exists())
        self.assertTrue((folder / "scene_abc.mp4").exists() and (folder / "photo0.jpg").exists(), "photos, plan and scene clips stay")
        self.assertTrue(film.get(quote["id"])["ok"], "and it can be retouched")
        (folder / "film.mp4").write_bytes(b"x")
        self.assertTrue(film.delete(quote["id"], drafts=True)["ok"])
        self.assertFalse(folder.exists())

    def test_saving_in_github_needs_the_connection_then_goes_by_the_api(self):
        from unittest import mock
        from aiwa_brain import github, state, studio
        film = self.make()
        quote = film.prepare("un film", photos=[b"jpg"], consent=True)
        job = film.jobs[quote["id"]]
        (job["dir"] / "film.mp4").write_bytes(b"x" * 2048)
        job["film"] = "film.mp4"
        old = studio.film
        studio.film = film
        state.current_repo = "me/site"
        try:
            with mock.patch.object(github, "token_value", return_value=None):
                answer = studio.film_publish(quote["id"])
            self.assertFalse(answer["ok"])
            self.assertEqual(answer["needs"], "github")
            sent = []
            with mock.patch.object(github, "token_value", return_value="t"), mock.patch.object(github, "release_upload", side_effect=lambda *a, **k: sent.append(a)), \
                    mock.patch("threading.Thread") as thread:
                self.assertTrue(studio.film_publish(quote["id"])["ok"])
                thread.call_args.kwargs["target"]()
            self.assertEqual(sent[0][0], "me/site")
            self.assertTrue(sent[0][1].startswith("video-film-"))
            self.assertEqual(film.get(quote["id"])["saved"], "saved")
        finally:
            studio.film = old
            state.current_repo = None


if __name__ == "__main__":
    unittest.main()
