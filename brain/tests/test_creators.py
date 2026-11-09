import hashlib
import json
import unittest
import unittest.mock

from aiwa_brain import creators, ed25519_lib, finder

def make_event(seed, source="export const rules = {}", name="rules", tamper=None):
    secret = hashlib.sha256(seed.encode()).digest()
    pub = ed25519_lib.public_key(secret).hex()
    author = hashlib.sha256(bytes.fromhex(pub)).hexdigest()
    payload = {"name": name, "version": "1", "sourceCode": source, "sourceHash": hashlib.sha256(source.encode()).hexdigest(), "description": "é"}
    core = {"domain": "d", "author": author, "authorPublicKey": pub, "parents": [], "type": "contract-spec", "payload": dict(sorted(payload.items())), "createdAt": 1700000000000}
    raw = json.dumps(core, separators=(",", ":"), ensure_ascii=False).encode()
    event = {"id": hashlib.sha256(raw).hexdigest(), **{k: core[k] for k in ("domain", "author", "authorPublicKey", "parents", "type", "payload", "createdAt")}, "signature": ed25519_lib.sign(secret, raw).hex()}
    if tamper:
        tamper(event)
    return pub, event


class Ed25519Test(unittest.TestCase):
    def test_rfc8032_vector(self):
        pub = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertTrue(ed25519_lib.verify(sig, b"", pub))
        self.assertFalse(ed25519_lib.verify(sig, b"x", pub))
        self.assertFalse(ed25519_lib.verify(sig[:-1] + b"\x00", b"", pub))
        self.assertFalse(ed25519_lib.verify(b"short", b"", pub))
        seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
        self.assertEqual(ed25519_lib.public_key(seed), pub)
        self.assertEqual(ed25519_lib.sign(seed, b""), sig)


class ContractsTest(unittest.TestCase):
    def test_a_genuine_event_counts(self):
        pub, event = make_event("a")
        self.assertTrue(creators.event_valid(event))
        found = creators.contracts_in({"v": 1, "creator": event["author"], "events": [event, event]}, pub)
        self.assertEqual([c["name"] for c in found], ["rules"])

    def test_altered_source_or_payload_or_signature_is_dropped(self):
        for tamper in (lambda e: e["payload"].update(sourceCode="evil"), lambda e: e["payload"].update(name="other"), lambda e: e.update(signature="0" * 128), lambda e: e.update(createdAt=1)):
            pub, event = make_event("a", tamper=tamper)
            self.assertFalse(creators.event_valid(event))
            self.assertEqual(creators.contracts_in({"v": 1, "events": [event]}, pub), [])

    def test_a_copied_file_counts_for_nothing_the_key_of_the_profile_must_have_signed(self):
        pub_a, event = make_event("a")
        pub_b, _ = make_event("b")
        self.assertEqual(creators.contracts_in({"v": 1, "events": [event]}, pub_b), [])
        self.assertEqual(len(creators.contracts_in({"v": 1, "events": [event]}, pub_a)), 1)

    def test_malformed_files(self):
        for data in (None, [], {"v": 2, "events": []}, {"v": 1, "events": "x"}, {"v": 1, "events": [None, 3, {"type": "contract-spec"}]}):
            self.assertEqual(creators.contracts_in(data, "a" * 64), [])
        self.assertEqual(creators.contracts_in({"v": 1, "events": []}, "not hex"), [])

    def test_of_reads_the_key_then_the_file(self):
        creators._cache.clear()
        pub, event = make_event("c")
        files = {"aiwa.json": {"v": 1, "pub": pub}, "aiwa-contracts.json": {"v": 1, "creator": event["author"], "events": [event]}}
        with unittest.mock.patch.object(creators, "_raw", side_effect=lambda repo, name, limit: files.get(name)):
            self.assertTrue(creators.of("x/y")["creator"])
        creators._cache.clear()
        with unittest.mock.patch.object(creators, "_raw", side_effect=lambda repo, name, limit: None if name == "aiwa.json" else files[name]):
            self.assertFalse(creators.of("x/y")["creator"])
        self.assertFalse(creators.of("not a repo")["ok"])


class FilterTest(unittest.TestCase):
    def test_filter_alone_lists_the_creators(self):
        with unittest.mock.patch.object(finder.creators, "listed", return_value=[("a/p", [1, 2]), ("b/p", [1])]):
            out = finder.find("", "creators")
        self.assertEqual((out["ok"], out["repos"], out["contracts"]), (True, ["a/p", "b/p"], {"a/p": 2, "b/p": 1}))

    def test_filter_keeps_only_the_creators_of_what_was_found(self):
        with unittest.mock.patch.object(finder, "terms", return_value=["v"]), unittest.mock.patch.object(finder, "_search", return_value=["a/p", "b/p", "c/p"]), \
                unittest.mock.patch.object(finder.creators, "creators_among", side_effect=lambda r: [("b/p", [1])]):
            out = finder.find("video", "creators")
        self.assertEqual(out["repos"], ["b/p"])

    def test_network_keeps_the_creators_among_her_people(self):
        seen = {}
        def among(repos):
            seen["pool"] = list(repos)
            return [(r, [1]) for r in repos if r == "n/p"]
        with unittest.mock.patch.object(finder, "_network", return_value=["n/p", "m/p"]), unittest.mock.patch.object(finder.creators, "creators_among", side_effect=among):
            out = finder.find("", "network", ["n/p"])
        self.assertEqual((out["repos"], seen["pool"]), (["n/p"], ["n/p", "m/p"]))
        with unittest.mock.patch.object(finder, "_network", return_value=["n/p"]), unittest.mock.patch.object(finder, "terms", return_value=["v"]), \
                unittest.mock.patch.object(finder, "_search", return_value=["N/P", "z/p"]), unittest.mock.patch.object(finder.creators, "creators_among", side_effect=among):
            finder.find("x", "network", [])
        self.assertEqual(seen["pool"], ["N/P"])

    def test_none_found_says_so_and_unknown_filter_is_ignored(self):
        with unittest.mock.patch.object(finder.creators, "listed", return_value=[]):
            out = finder.find("", "creators")
        self.assertEqual((out["repos"], out["error"]), ([], "aucun créateur trouvé"))
        self.assertFalse(finder.find("", "bogus")["ok"])

    def test_a_refusal_of_github_is_said(self):
        with unittest.mock.patch.object(finder.creators, "listed", side_effect=RuntimeError("GitHub limite")):
            out = finder.find("", "creators")
        self.assertEqual((out["ok"], out["error"]), (False, "GitHub limite"))


if __name__ == "__main__":
    unittest.main()
