"""
Voice Activity Detection (VAD) and Silence Detection for LinuxOpsAssistant.

Provides audio energy calculation, adaptive background noise thresholding,
and silence duration tracking to auto-stop voice recording when the user finishes speaking.
"""

from __future__ import annotations

import math
import struct
from typing import List, Optional, Tuple


class VoiceActivityDetector:
    """Calculates RMS audio energy and determines active speech vs background silence."""

    def __init__(
        self,
        energy_threshold: float = 300.0,
        silence_timeout_sec: float = 1.5,
        min_speech_duration_sec: float = 0.4,
        sample_rate: int = 16000,
        sample_width: int = 2,  # 16-bit PCM = 2 bytes
        channels: int = 1,
    ):
        self.energy_threshold = energy_threshold
        self.silence_timeout_sec = silence_timeout_sec
        self.min_speech_duration_sec = min_speech_duration_sec
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.channels = channels

        self._consecutive_silence_sec = 0.0
        self._total_speech_sec = 0.0
        self._has_speech_started = False
        self._background_noise_level = energy_threshold * 0.5
        self._adaptive_noise = True

    def reset(self):
        """Resets detector state for a new recording session."""
        self._consecutive_silence_sec = 0.0
        self._total_speech_sec = 0.0
        self._has_speech_started = False

    def calculate_rms(self, pcm_data: bytes) -> float:
        """Calculates Root Mean Square (RMS) energy of 16-bit PCM audio chunk."""
        if not pcm_data:
            return 0.0

        count = len(pcm_data) // 2
        if count == 0:
            return 0.0

        shorts = struct.unpack(f"<{count}h", pcm_data[: count * 2])
        sum_squares = sum(s * s for s in shorts)
        mean_square = sum_squares / count
        return math.sqrt(mean_square)

    def process_chunk(self, pcm_chunk: bytes, chunk_duration_sec: float) -> Tuple[bool, bool, float]:
        """
        Processes an incoming audio chunk.

        Returns:
            (is_speaking: bool, should_stop: bool, rms_energy: float)
        """
        rms = self.calculate_rms(pcm_chunk)

        # Dynamic threshold adjustment for background noise
        if self._adaptive_noise and not self._has_speech_started:
            self._background_noise_level = (self._background_noise_level * 0.9) + (rms * 0.1)
            effective_threshold = max(self.energy_threshold, self._background_noise_level * 1.8)
        else:
            effective_threshold = self.energy_threshold

        is_speaking = rms >= effective_threshold

        if is_speaking:
            self._has_speech_started = True
            self._total_speech_sec += chunk_duration_sec
            self._consecutive_silence_sec = 0.0
        else:
            if self._has_speech_started:
                self._consecutive_silence_sec += chunk_duration_sec

        # Stop condition: User has spoken for minimum duration, and then paused for silence_timeout_sec
        should_stop = (
            self._has_speech_started
            and (self._total_speech_sec >= self.min_speech_duration_sec)
            and (self._consecutive_silence_sec >= self.silence_timeout_sec)
        )

        return is_speaking, should_stop, rms

    def get_meter_bars(self, rms: float, max_bars: int = 8) -> str:
        """Generates an ASCII/Unicode volume meter for live UI display."""
        ratio = min(1.0, max(0.0, rms / (self.energy_threshold * 4.0)))
        bars = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        idx = int(ratio * (len(bars) - 1))
        active_bar = bars[idx]
        return active_bar * max_bars
