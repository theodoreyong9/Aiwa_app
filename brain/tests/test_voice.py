import tempfile, unittest, unittest.mock, wave, io
from aiwa_brain import voice_lib as v


class VoiceTest(unittest.TestCase):
    def test_wav_is_a_16_bit_mono_file_with_the_right_length(self):
        data = v.to_wav([0.0, 0.5, -0.5, 2.0, -2.0], 22050)
        w = wave.open(io.BytesIO(data))
        self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 2, 22050, 5))
        frames = w.readframes(5)
        self.assertEqual(int.from_bytes(frames[6:8], "little", signed=True), 32767)    # clipped, not wrapped
        self.assertEqual(int.from_bytes(frames[8:10], "little", signed=True), -32767)

    def test_nothing_is_said_when_the_voice_is_not_installed(self):
        with tempfile.TemporaryDirectory() as home:
            voice = v.Voice(home)
            self.assertEqual(voice.state, "none")
            self.assertIsNone(voice.say("Bonjour"))
            self.assertFalse(v.model_present(home))


if __name__ == "__main__":
    unittest.main()


class PipInstallTests(unittest.TestCase):
    def test_retries_with_break_system_packages_when_the_python_is_externally_managed(self):
        import subprocess
        calls = []

        def fake(cmd, **kw):
            calls.append(cmd)
            if "--break-system-packages" in cmd:
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 1, "", "error: externally-managed-environment")
        with unittest.mock.patch.object(v.subprocess, "run", fake):
            v.pip_install("sherpa-onnx")
        self.assertEqual(len(calls), 2)

    def test_failure_carries_pips_own_words(self):
        import subprocess
        with unittest.mock.patch.object(v.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "ERROR: no matching distribution")):
            with self.assertRaises(RuntimeError) as ctx:
                v.pip_install("sherpa-onnx")
        self.assertIn("no matching distribution", str(ctx.exception))


class SelfHealingTests(unittest.TestCase):
    def _ready(self, home):
        voice = v.Voice(home)
        voice.state = "ready"
        return voice

    def test_one_failed_sentence_does_not_take_the_voice_away_but_three_in_a_row_do(self):
        import sys
        broken = unittest.mock.MagicMock()
        broken.OfflineTts.side_effect = RuntimeError("boom")
        with tempfile.TemporaryDirectory() as home, unittest.mock.patch.dict(sys.modules, {"sherpa_onnx": broken}):
            voice = self._ready(home)
            self.assertIsNone(voice.say("Un"))
            self.assertEqual(voice.state, "ready")
            self.assertIsNone(voice.say("Deux"))
            self.assertEqual(voice.state, "ready")
            self.assertIsNone(voice.say("Trois"))
            self.assertEqual(voice.state, "error")
            self.assertIn("boom", voice.error)

    def test_a_voice_in_error_is_installed_again_after_a_while_not_before(self):
        with tempfile.TemporaryDirectory() as home:
            voice = v.Voice(home)
            voice.state, voice.attempt_at = "error", 1000.0
            with unittest.mock.patch.object(v.time, "time", return_value=1100.0), unittest.mock.patch.object(voice, "install") as install:
                voice.retry_if_failed(wait=600)
                install.assert_not_called()
            with unittest.mock.patch.object(v.time, "time", return_value=1700.0), unittest.mock.patch.object(voice, "install") as install:
                voice.retry_if_failed(wait=600)
                install.assert_called_once()
