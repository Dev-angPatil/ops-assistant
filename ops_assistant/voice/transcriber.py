"""
Multi-Engine Speech Transcription and Phonetic Normalizer for LinuxOpsAssistant.

Handles audio transcription across English, Hinglish, and Indian accents with
specialized phonetic error-correction for Linux technical vocabulary.
"""

from __future__ import annotations

import io
import re
import os
import wave
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PhoneticNormalizer:
    """Corrects common speech-recognition phonetic errors in Linux sysadmin vocabulary."""

    # Phonetic and spoken phrasing replacements
    REPLACEMENTS: List[Tuple[re.Pattern, str]] = [
        # Package managers & privileges
        (re.compile(r"\b(?:apt\s+get|app\s+get|ab\s+get)\b", re.IGNORECASE), "apt-get"),
        (re.compile(r"\b(?:pseudo|su\s+do|sue\s+dough|soodo)\b", re.IGNORECASE), "sudo"),
        (re.compile(r"\b(?:pac\s+man|pack\s+man)\b", re.IGNORECASE), "pacman"),
        (re.compile(r"\b(?:yum\s+install|d\s+n\s+f)\b", re.IGNORECASE), "dnf"),
        
        # Systemd and log binaries
        (re.compile(r"\b(?:system\s+control|system\s+ctl|system\s+control\s+l)\b", re.IGNORECASE), "systemctl"),
        (re.compile(r"\b(?:journal\s+control|journal\s+ctl|journal\s+see\s+tee\s+el)\b", re.IGNORECASE), "journalctl"),
        (re.compile(r"\b(?:d\s+message|d\s+msg|dee\s+mesg)\b", re.IGNORECASE), "dmesg"),
        (re.compile(r"\b(?:engine\s+x|engine\s+ex|n\s+jinx|n\s+ginx)\b", re.IGNORECASE), "nginx"),
        (re.compile(r"\b(?:cron\s+tab|chron\s+tab)\b", re.IGNORECASE), "crontab"),
        (re.compile(r"\b(?:h\s+top|age\s+top)\b", re.IGNORECASE), "htop"),
        (re.compile(r"\b(?:if\s+config)\b", re.IGNORECASE), "ifconfig"),
        (re.compile(r"\b(?:net\s+stat)\b", re.IGNORECASE), "netstat"),
        
        # Docker and containers
        (re.compile(r"\b(?:docker\s+composed|docker\s+compose\s+up)\b", re.IGNORECASE), "docker compose"),
        (re.compile(r"\b(?:docker\s+container\s+p\s+s)\b", re.IGNORECASE), "docker ps"),
        (re.compile(r"\b(?:cube\s+c\s+t\s+l|kube\s+control|cube\s+control)\b", re.IGNORECASE), "kubectl"),

        # Common phonetic search / text tools
        (re.compile(r"\b(?:grab|grip|grape)\s+(?:for\s+)?(?P<term>error|failed|warning|log|port|process|service|ip|user)\b", re.IGNORECASE), r"grep \g<term>"),
        (re.compile(r"\b(?:target\s+z|tar\s+gz|tar\s+ball)\b", re.IGNORECASE), "tar.gz"),
        (re.compile(r"\b(?:zip\s+file|un\s+zip)\b", re.IGNORECASE), "unzip"),

        # Typo and pronunciation smoothing for folders & files
        (re.compile(r"\b(?:downlaods|downlods|down\s+loads)\b", re.IGNORECASE), "downloads"),
        (re.compile(r"\b(?:documnts|documants|docments)\b", re.IGNORECASE), "documents"),
        (re.compile(r"\b(?:picturs|picshurs)\b", re.IGNORECASE), "pictures"),
        (re.compile(r"\b(?:floder|foldr)\b", re.IGNORECASE), "folder"),
        (re.compile(r"\b(?:direc\s+tree|dirctory)\b", re.IGNORECASE), "directory"),
        (re.compile(r"\b(?:d\s+s\s+a)\b", re.IGNORECASE), "DSA"),
        (re.compile(r"\b(?:p\s+d\s+f|p\s+d\s+f\s+s)\b", re.IGNORECASE), "PDF"),
        (re.compile(r"\b(?:c\s+p\s+u)\b", re.IGNORECASE), "CPU"),
        (re.compile(r"\b(?:r\s+a\s+m)\b", re.IGNORECASE), "RAM"),
        (re.compile(r"\b(?:i\s+p)\b", re.IGNORECASE), "IP"),

        # Hinglish / Indian English Translative Normalizations
        (re.compile(r"\b(?P<target>.+)\s+(?:kholo|khol\s+do|open\s+karo)\b", re.IGNORECASE), r"open \g<target>"),
        (re.compile(r"\b(?P<target>.+)\s+(?:dikhao|batao|check\s+karo)\b", re.IGNORECASE), r"show \g<target>"),
        (re.compile(r"\b(?P<target>.+)\s+(?:chalu\s+karo|start\s+karo|shuru\s+karo)\b", re.IGNORECASE), r"start \g<target>"),
        (re.compile(r"\b(?P<target>.+)\s+(?:band\s+karo|rok\s+do|stop\s+karo)\b", re.IGNORECASE), r"stop \g<target>"),
        (re.compile(r"\b(?P<target>.+)\s+(?:hatao|mitao|delete\s+karo|ura\s+do)\b", re.IGNORECASE), r"delete \g<target>"),
        (re.compile(r"\b(?:kitna|kitni)\s+(?:ram|memory|space|storage|disk)\s+(?:baki|free|use)\s*(?:hai)?\b", re.IGNORECASE), r"check memory usage"),
    ]

    @classmethod
    def normalize(cls, text: str) -> str:
        """Applies phonetic and lexical normalization rules to transcribed voice text."""
        if not text:
            return ""

        cleaned = text.strip()
        for pattern, replacement in cls.REPLACEMENTS:
            cleaned = pattern.sub(replacement, cleaned)

        # Cleanup redundant spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


class SpeechTranscriber:
    """Multi-engine speech-to-text pipeline with phonetic correction and confidence estimation."""

    def __init__(self, default_language: str = "en-IN"):
        self.default_language = default_language
        self.normalizer = PhoneticNormalizer()

    def transcribe_wav_bytes(self, wav_bytes: bytes, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Transcribes standard RIFF WAV bytes into text.

        Returns:
            {
                "success": bool,
                "text": str,
                "raw_text": str,
                "confidence": float,
                "engine": str,
                "needs_confirmation": bool,
                "confirmation_prompt": Optional[str]
            }
        """
        if not wav_bytes or len(wav_bytes) < 100:
            return {
                "success": False,
                "text": "",
                "raw_text": "",
                "confidence": 0.0,
                "engine": "none",
                "error": "Audio stream is empty or too short."
            }

        lang = language or self.default_language

        # 1. Try SpeechRecognition library (Google STT / Sphinx / Whisper)
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = recognizer.record(source)

            # Try online Google Speech Recognition (free public API in speech_recognition)
            try:
                raw_text = recognizer.recognize_google(audio, language=lang)
                clean_text = self.normalizer.normalize(raw_text)
                return {
                    "success": True,
                    "text": clean_text,
                    "raw_text": raw_text,
                    "confidence": 0.94,
                    "engine": "google_speech_api",
                    "needs_confirmation": False
                }
            except Exception:
                # Fallback to Sphinx / offline recognition if installed
                try:
                    raw_text = recognizer.recognize_sphinx(audio)
                    clean_text = self.normalizer.normalize(raw_text)
                    return {
                        "success": True,
                        "text": clean_text,
                        "raw_text": raw_text,
                        "confidence": 0.75,
                        "engine": "sphinx_offline",
                        "needs_confirmation": True,
                        "confirmation_prompt": f"I heard: '{clean_text}'. Is that correct?"
                    }
                except Exception:
                    pass
        except ImportError:
            pass

        # 2. Try faster-whisper / whisper if installed
        try:
            import whisper
            model = whisper.load_model("tiny")
            with io.BytesIO(wav_bytes) as audio_file:
                result = model.transcribe(audio_file)
                raw_text = result.get("text", "").strip()
                clean_text = self.normalizer.normalize(raw_text)
                return {
                    "success": True,
                    "text": clean_text,
                    "raw_text": raw_text,
                    "confidence": 0.92,
                    "engine": "whisper_tiny",
                    "needs_confirmation": False
                }
        except Exception:
            pass

        # 3. Fallback: Return structured notice for GUI Web Speech API / Direct text input
        return {
            "success": False,
            "text": "",
            "raw_text": "",
            "confidence": 0.0,
            "engine": "fallback",
            "error": "No offline STT engine is loaded. Use Web Speech in GUI or enter text in terminal."
        }
