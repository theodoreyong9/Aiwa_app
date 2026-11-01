"""The scenarios kept on GitHub too: one file each, written when changed, deleted when deleted, read back after a reinstallation, defaults left out."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aiwa_brain import config, links, scen_lib, scen_sync


class ScenSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        patches = [mock.patch.object(config, "SCENARIOS_FILE", base / "scenarios.json"), mock.patch.object(scen_sync, "STATE", base / "sync.json"),
                   mock.patch.object(scen_sync.profile_lib, "repo", return_value="me/me"), mock.patch.object(scen_sync.github, "token_value", return_value="t")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.mine = {"id": "mon", "name": "Mon scénario", "word": "mon scénario", "kind": "double", "prompt": "fais ceci", "speak": "", "words": []}
        scen_lib.save(config.SCENARIOS_FILE, [self.mine] + scen_lib.DEFAULTS)

    def test_a_changed_scenario_is_written_once_and_the_defaults_never(self):
        with mock.patch.object(scen_sync.github, "put_file") as put:
            first = scen_sync.push_all()
            second = scen_sync.push_all()
        self.assertEqual((first["ok"], first["written"], second["written"]), (True, 1, 0))
        self.assertEqual(put.call_args[0][1], "Profile/scenarios/mon.json")

    def test_a_scenario_deleted_here_is_deleted_there(self):
        with mock.patch.object(scen_sync.github, "put_file"):
            scen_sync.push_all()
        scen_lib.save(config.SCENARIOS_FILE, list(scen_lib.DEFAULTS))
        with mock.patch.object(scen_sync.github, "delete_file") as gone:
            out = scen_sync.push_all()
        self.assertEqual(out["deleted"], 1)
        self.assertEqual(gone.call_args[0][1], "Profile/scenarios/mon.json")

    def test_after_a_reinstallation_the_scenarios_come_back_and_nothing_here_is_replaced(self):
        scen_lib.save(config.SCENARIOS_FILE, list(scen_lib.DEFAULTS))
        other = dict(self.mine, id="autre", name="Autre", word="mot autre", prompt="remote")
        listing = [{"name": "mon.json", "download_url": "https://x/mon.json"}, {"name": "autre.json", "download_url": "https://x/autre.json"}, {"name": "note.txt", "download_url": "https://x/n"}]
        bodies = {"https://x/mon.json": json.dumps(self.mine).encode(), "https://x/autre.json": json.dumps(other).encode()}
        with mock.patch.object(scen_sync.github, "api", return_value=listing), mock.patch.object(scen_sync.github, "fetch", side_effect=lambda url, limit: bodies[url]):
            out = scen_sync.pull()
        self.assertEqual(out["added"], 2)
        self.assertEqual({s["id"] for s in scen_lib.load(config.SCENARIOS_FILE)} >= {"mon", "autre"}, True)

    def test_without_a_profile_repository_nothing_is_written(self):
        with mock.patch.object(scen_sync.profile_lib, "repo", return_value=None):
            self.assertFalse(scen_sync.push_all()["ok"])


class PjOnGithubTests(unittest.TestCase):
    def test_the_links_are_read_back_from_the_release_when_the_phone_has_none(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(links, "FILE", Path(tmp) / "links.json"), mock.patch.object(links.github, "token_value", return_value="t"):
            release = [{"tag": "docs-valeur", "assets": [{"name": "valeur.pdf.pj.json", "url": "https://x/pj"}]}]
            body = json.dumps({"v": 1, "pj": {"a@b.fr": [{"repo": "me/app", "tag": "docs-cv", "file": "cv.pdf"}]}}).encode()
            with mock.patch.object(links.github, "releases", return_value=release), mock.patch.object(links.github, "fetch", return_value=body):
                got = links.get("me/app", "docs-valeur", "valeur.pdf")
            self.assertEqual(got["a@b.fr"][0]["file"], "cv.pdf")
            with mock.patch.object(links.github, "releases", side_effect=AssertionError("kept on the phone now")):
                self.assertEqual(links.get("me/app", "docs-valeur", "valeur.pdf")["a@b.fr"][0]["file"], "cv.pdf")


if __name__ == "__main__":
    unittest.main()
