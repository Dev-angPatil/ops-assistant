"""
Unit Tests for Voice and Speech Processing Subsystem.
"""

import pytest
import struct
from ops_assistant.voice.vad import VoiceActivityDetector
from ops_assistant.voice.transcriber import PhoneticNormalizer, SpeechTranscriber
from ops_assistant.voice.recorder import VoiceRecorder


def test_vad_rms_calculation():
    vad = VoiceActivityDetector(energy_threshold=300.0)
    # Zero audio
    assert vad.calculate_rms(b"") == 0.0

    # Sine/square wave simulation
    samples = [1000, -1000, 1000, -1000] * 100
    pcm = struct.pack(f"<{len(samples)}h", *samples)
    rms = vad.calculate_rms(pcm)
    assert rms == pytest.approx(1000.0, rel=1e-2)


def test_vad_silence_detection():
    vad = VoiceActivityDetector(energy_threshold=300.0, silence_timeout_sec=0.2, min_speech_duration_sec=0.1)

    # 1. Loud speech chunk
    loud_samples = [1500] * 1024
    loud_pcm = struct.pack(f"<{len(loud_samples)}h", *loud_samples)
    is_spk, should_stop, _ = vad.process_chunk(loud_pcm, 0.15)
    assert is_spk is True
    assert should_stop is False

    # 2. Silence chunk
    silent_samples = [10] * 1024
    silent_pcm = struct.pack(f"<{len(silent_samples)}h", *silent_samples)
    is_spk2, should_stop2, _ = vad.process_chunk(silent_pcm, 0.25)
    assert is_spk2 is False
    assert should_stop2 is True


def test_vad_meter_bars():
    vad = VoiceActivityDetector(energy_threshold=300.0)
    bars = vad.get_meter_bars(1200.0, max_bars=6)
    assert len(bars) == 6
    assert isinstance(bars, str)


def test_phonetic_normalizer():
    norm = PhoneticNormalizer()
    assert norm.normalize("sudo apt get update") == "sudo apt-get update"
    assert norm.normalize("pseudo system control restart nginx") == "sudo systemctl restart nginx"
    assert norm.normalize("journal control for errors") == "journalctl for errors"
    assert norm.normalize("grab error from syslog") == "grep error from syslog"
    assert norm.normalize("open downlaods floder") == "open downloads folder"
    assert norm.normalize("create d s a floder") == "create DSA folder"


def test_hinglish_normalizer():
    norm = PhoneticNormalizer()
    assert norm.normalize("downloads kholo") == "open downloads"
    assert norm.normalize("cpu usage dikhao") == "show cpu usage"
    assert norm.normalize("firefox chalu karo") == "start firefox"
    assert norm.normalize("project delete karo") == "delete project"


def test_voice_recorder_availability():
    rec = VoiceRecorder()
    avail, details = rec.is_microphone_available()
    assert isinstance(avail, bool)
    assert isinstance(details, str)


def test_speech_transcriber_empty_wav():
    transcriber = SpeechTranscriber()
    res = transcriber.transcribe_wav_bytes(b"")
    assert res["success"] is False
    assert "empty" in res["error"].lower()
