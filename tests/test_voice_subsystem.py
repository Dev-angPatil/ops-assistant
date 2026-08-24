"""
Unit Tests for Voice and Speech Processing Subsystem.
"""

import struct
import unittest
from ops_assistant.voice.vad import VoiceActivityDetector
from ops_assistant.voice.transcriber import PhoneticNormalizer, SpeechTranscriber
from ops_assistant.voice.recorder import VoiceRecorder


class TestVoiceSubsystem(unittest.TestCase):

    def test_vad_rms_calculation(self):
        vad = VoiceActivityDetector(energy_threshold=300.0)
        # Zero audio
        self.assertEqual(vad.calculate_rms(b""), 0.0)

        # Sine/square wave simulation
        samples = [1000, -1000, 1000, -1000] * 100
        pcm = struct.pack(f"<{len(samples)}h", *samples)
        rms = vad.calculate_rms(pcm)
        self.assertAlmostEqual(rms, 1000.0, delta=10.0)

    def test_vad_silence_detection(self):
        vad = VoiceActivityDetector(energy_threshold=300.0, silence_timeout_sec=0.2, min_speech_duration_sec=0.1)

        # 1. Loud speech chunk
        loud_samples = [1500] * 1024
        loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
        is_spk, should_stop, _ = vad.process_chunk(loud_pcm, 0.15)
        self.assertTrue(is_spk)
        self.assertFalse(should_stop)

        # 2. Silence chunk
        silent_samples = [10] * 1024
        silent_pcm = struct.pack(f"<{len(silent_samples)}h", *silent_samples)
        is_spk2, should_stop2, _ = vad.process_chunk(silent_pcm, 0.25)
        self.assertFalse(is_spk2)
        self.assertTrue(should_stop2)

    def test_vad_meter_bars(self):
        vad = VoiceActivityDetector(energy_threshold=300.0)
        bars = vad.get_meter_bars(1200.0, max_bars=6)
        self.assertEqual(len(bars), 6)
        self.assertIsInstance(bars, str)

    def test_phonetic_normalizer(self):
        norm = PhoneticNormalizer()
        self.assertEqual(norm.normalize("sudo apt get update"), "sudo apt-get update")
        self.assertEqual(norm.normalize("pseudo system control restart nginx"), "sudo systemctl restart nginx")
        self.assertEqual(norm.normalize("journal control for errors"), "journalctl for errors")
        self.assertEqual(norm.normalize("grab error from syslog"), "grep error from syslog")
        self.assertEqual(norm.normalize("open downlaods floder"), "open downloads folder")
        self.assertEqual(norm.normalize("create d s a floder"), "create DSA folder")

    def test_hinglish_normalizer(self):
        norm = PhoneticNormalizer()
        self.assertEqual(norm.normalize("downloads kholo"), "open downloads")
        self.assertEqual(norm.normalize("cpu usage dikhao"), "show cpu usage")
        self.assertEqual(norm.normalize("firefox chalu karo"), "start firefox")
        self.assertEqual(norm.normalize("project delete karo"), "delete project")

    def test_voice_recorder_availability(self):
        rec = VoiceRecorder()
        avail, details = rec.is_microphone_available()
        self.assertIsInstance(avail, bool)
        self.assertIsInstance(details, str)

    def test_speech_transcriber_empty_wav(self):
        transcriber = SpeechTranscriber()
        res = transcriber.transcribe_wav_bytes(b"")
        self.assertFalse(res["success"])
        self.assertIn("empty", res["error"].lower())


if __name__ == "__main__":
    unittest.main()
