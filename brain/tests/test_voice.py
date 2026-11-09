import tempfile, time, unittest, unittest.mock, wave, io
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



class EngineTests(unittest.TestCase):
    """Two engines: Piper (light, the default) and Kokoro (heavy, on request, only while it keeps up)."""

    class Audio:
        def __init__(self, seconds):
            self.samples = [0.0] * int(seconds * 1000)
            self.sample_rate = 1000

    class Fake:
        def __init__(self, seconds=2.0, delay=0.0, boom=False):
            self.seconds, self.delay, self.boom = seconds, delay, boom

        def generate(self, text, sid=0, speed=1.0):
            if self.boom:
                raise RuntimeError("boom")
            if self.delay:
                time.sleep(self.delay)
            return EngineTests.Audio(self.seconds)

    def _voice(self, home, kokoro_ready=True):
        voice = v.Voice(home)
        voice.state = "ready"
        voice.kokoro = "ready" if kokoro_ready else "none"
        return voice

    def test_piper_is_the_default_and_an_unknown_engine_is_refused(self):
        with tempfile.TemporaryDirectory() as home:
            voice = v.Voice(home)
            self.assertEqual(voice.engine, "piper")
            self.assertFalse(voice.set_engine("elevenlabs")["ok"])
            self.assertEqual(voice.engine, "piper")

    def test_the_choice_is_kept_between_two_runs(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home)
            voice.set_engine("kokoro")
            self.assertEqual(v.read_engine(home), "kokoro")
            self.assertEqual(v.Voice(home).engine, "kokoro")

    def test_the_heavy_engine_is_downloaded_on_request_and_the_light_one_speaks_meanwhile(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home, kokoro_ready=False)
            with unittest.mock.patch.object(v.Voice, "install_kokoro") as install:
                out = voice.set_engine("kokoro")
            install.assert_called_once()
            self.assertTrue(out["ok"])
            self.assertEqual(voice.engine, "kokoro")
            self.assertEqual(voice.active(), "piper")        # Kokoro is not there yet: Piper speaks

    def test_nothing_is_downloaded_when_the_light_engine_is_chosen(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home, kokoro_ready=False)
            with unittest.mock.patch.object(v.Voice, "install_kokoro") as install:
                voice.set_engine("piper")
            install.assert_not_called()

    def test_a_heavy_engine_that_is_too_slow_twice_in_a_row_gives_the_voice_back_to_piper(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home)
            voice.set_engine("kokoro")
            with unittest.mock.patch.object(v.Voice, "_load", lambda self, engine: EngineTests.Fake(seconds=1.0, delay=1.3)), unittest.mock.patch.object(v, "SLOW", 1.0):
                self.assertIsNotNone(voice.say("Un"))
                self.assertEqual(voice.engine, "kokoro")                # once is not enough
                self.assertIsNotNone(voice.say("Deux"))
            self.assertEqual(voice.engine, "piper")
            self.assertIn("trop lent", voice.note)
            self.assertEqual(v.read_engine(home), "piper")

    def test_a_heavy_engine_that_keeps_up_stays(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home)
            voice.set_engine("kokoro")
            with unittest.mock.patch.object(v.Voice, "_load", lambda self, engine: EngineTests.Fake(seconds=2.0, delay=0.2)):
                for _ in range(3):
                    self.assertIsNotNone(voice.say("Une phrase"))
            self.assertEqual(voice.engine, "kokoro")
            self.assertIsNone(voice.note)

    def test_a_heavy_engine_that_fails_three_times_gives_the_voice_back_to_piper_without_taking_it_away(self):
        with tempfile.TemporaryDirectory() as home:
            voice = self._voice(home)
            voice.set_engine("kokoro")
            with unittest.mock.patch.object(v.Voice, "_load", lambda self, engine: EngineTests.Fake(boom=True)):
                for _ in range(3):
                    self.assertIsNone(voice.say("Un"))
            self.assertEqual(voice.engine, "piper")
            self.assertEqual(voice.state, "ready")                       # the light engine is still there
            with unittest.mock.patch.object(v.Voice, "_load", lambda self, engine: EngineTests.Fake()):
                self.assertIsNotNone(voice.say("Et Piper parle"))


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
        with unittest.mock.patch.object(v, "_pip_available", return_value=True), unittest.mock.patch.object(v.subprocess, "run", fake):
            v.pip_install("sherpa-onnx")
        self.assertEqual(len(calls), 2)

    def test_failure_carries_pips_own_words(self):
        import subprocess
        with unittest.mock.patch.object(v, "_pip_available", return_value=True), unittest.mock.patch.object(v.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "ERROR: no matching distribution")):
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


class EnsurePipTests(unittest.TestCase):
    def test_pip_is_installed_from_the_debian_package_when_the_python_has_none(self):
        import subprocess
        calls = []
        have = {"pip": False}

        def fake(cmd, **kw):
            calls.append(cmd)
            if cmd[:2] == ["apt-get", "install"]:
                have["pip"] = True
                return subprocess.CompletedProcess(cmd, 0, "", "")
            if "pip" in cmd and "--version" in cmd:
                return subprocess.CompletedProcess(cmd, 0 if have["pip"] else 1, "", "No module named pip")
            if "ensurepip" in cmd:
                return subprocess.CompletedProcess(cmd, 1, "", "ensurepip is disabled in Debian/Ubuntu")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        with unittest.mock.patch.object(v.subprocess, "run", fake):
            v.ensure_pip()
        self.assertTrue(any(c[:2] == ["apt-get", "install"] for c in calls))
        self.assertTrue(have["pip"])

    def test_it_says_so_when_nothing_gives_a_pip(self):
        import subprocess
        def fake(cmd, **kw):
            return subprocess.CompletedProcess(cmd, 1, "", "nope")
        with unittest.mock.patch.object(v.subprocess, "run", fake), unittest.mock.patch.object(v.urllib.request, "urlretrieve", side_effect=OSError("hors ligne")):
            with self.assertRaises(RuntimeError) as ctx:
                v.ensure_pip()
        self.assertIn("pip est absent", str(ctx.exception))
