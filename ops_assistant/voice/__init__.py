"""
Voice and Speech Processing Subsystem for LinuxOpsAssistant.

Exports:
- VoiceRecorder: Non-blocking audio capture with VAD
- VoiceActivityDetector: RMS audio energy and silence detector
- SpeechTranscriber: Speech-to-text pipeline
- PhoneticNormalizer: Technical Linux phonetic corrector
"""

from ops_assistant.voice.vad import VoiceActivityDetector
from ops_assistant.voice.recorder import VoiceRecorder
from ops_assistant.voice.transcriber import SpeechTranscriber, PhoneticNormalizer

__all__ = [
    "VoiceActivityDetector",
    "VoiceRecorder",
    "SpeechTranscriber",
    "PhoneticNormalizer",
]
