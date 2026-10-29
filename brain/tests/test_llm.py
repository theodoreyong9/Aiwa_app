import os, stat, tempfile, unittest
from aiwa_brain import llm_lib as L

KEY = "sk-ant-api03-" + "a" * 30


class FakeBlock:
    type = "text"
    def __init__(self, text): self.text = text


class FakeResponse:
    stop_reason = "end_turn"
    def __init__(self, text): self.content = [FakeBlock(text)]


class FakeClient:
    def __init__(self, key, text='{"say": "ok"}'):
        self.key, self.text, self.calls = key, text, []
        self.messages = self
    def create(self, **kw):
        self.calls.append(kw)
        return FakeResponse(self.text)


class LlmTest(unittest.TestCase):
    def make(self):
        d = tempfile.mkdtemp()
        holder = {}
        def factory(key):
            holder["c"] = FakeClient(key)
            return holder["c"]
        return L.Llm(os.path.join(d, "key"), factory), holder

    def test_no_key_means_nothing_runs(self):
        llm, _ = self.make()
        self.assertEqual(llm.state, "none")
        self.assertIsNone(llm.ask("s", [{"role": "user", "content": "x"}]))

    def test_a_bad_key_is_refused_and_a_good_one_is_kept_for_its_owner_only(self):
        llm, _ = self.make()
        self.assertFalse(llm.save_key("pas une clé")["ok"])
        self.assertTrue(llm.save_key(KEY)["ok"])
        self.assertEqual(stat.S_IMODE(os.stat(llm.key_file).st_mode), 0o600)
        self.assertEqual(llm.state, "ready")
        self.assertTrue(llm.clear_key()["ok"])
        self.assertEqual(llm.state, "none")

    def test_it_answers_with_the_key_and_the_json_is_found_in_words(self):
        llm, holder = self.make()
        llm.save_key(KEY)
        text = llm.ask("système", [{"role": "user", "content": "salut"}])
        self.assertEqual(text, '{"say": "ok"}')
        self.assertEqual(holder["c"].key, KEY)
        self.assertEqual(holder["c"].calls[0]["model"], "claude-haiku-5-5")
        self.assertEqual(L.json_in('Voici : ```json\n{"say": "a } b", "do": {"model": "opus"}}\n``` fin'), {"say": "a } b", "do": {"model": "opus"}})
        self.assertIsNone(L.json_in("rien"))


if __name__ == "__main__":
    unittest.main()
