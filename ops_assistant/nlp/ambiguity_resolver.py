"""
Ambiguity Resolver for LinuxOpsAssistant.

Detects underspecified commands, multiple resource matches, and missing arguments
to solicit interactive clarification instead of guessing or executing unintended operations.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AmbiguityResolution:
    """Represents the ambiguity analysis of a user query."""
    is_ambiguous: bool = False
    ambiguity_type: Optional[str] = None  # "multiple_candidates", "missing_entity", "low_confidence_voice"
    prompt: Optional[str] = None
    candidates: List[str] = field(default_factory=list)
    action_template: Optional[str] = None
    suggested_action: Optional[str] = None


class AmbiguityResolver:
    """Analyzes queries and system state to prevent ambiguous execution."""

    @classmethod
    def check_ambiguity(
        cls,
        query: str,
        active_directory: Optional[str] = None,
        confidence: float = 1.0,
    ) -> AmbiguityResolution:
        q = query.strip()
        q_lower = q.lower()
        active_dir = Path(active_directory or os.getcwd()).expanduser()

        # 1. Low Confidence Voice Transcription Check
        if confidence < 0.70 and confidence > 0.0:
            return AmbiguityResolution(
                is_ambiguous=True,
                ambiguity_type="low_confidence_voice",
                prompt=f"I heard: '{query}'. Is that correct?",
                candidates=["Yes, continue", "No, cancel / re-speak"],
                suggested_action=query,
            )

        # 2. Ambiguous Project Reference: e.g. "Delete my project", "Open my project", "Remove the project"
        project_match = re.search(r"^(?:delete|remove|open|erase|trash)\s+(?:my\s+|the\s+)?project\s*$", q_lower)
        if project_match:
            verb = "delete" if any(v in q_lower for v in ("delete", "remove", "erase", "trash")) else "open"
            # Scan potential project directories
            candidates: List[str] = []
            search_dirs = [
                Path.home() / "Projects",
                Path.home() / "Documents",
                Path.home() / "code",
                Path.home() / "workspace",
                active_dir,
            ]
            for s_dir in search_dirs:
                if s_dir.exists() and s_dir.is_dir():
                    try:
                        for entry in s_dir.iterdir():
                            if entry.is_dir() and not entry.name.startswith((".", "node_modules", "venv", "__pycache__")):
                                if entry.name not in candidates:
                                    candidates.append(entry.name)
                    except Exception:
                        pass

            if len(candidates) > 1:
                return AmbiguityResolution(
                    is_ambiguous=True,
                    ambiguity_type="multiple_candidates",
                    prompt=f"I found multiple projects. Which one do you want to {verb}?",
                    candidates=candidates[:6],
                    action_template=f"{verb} project {{choice}}",
                )
            elif len(candidates) == 1:
                return AmbiguityResolution(
                    is_ambiguous=False,
                    suggested_action=f"{verb} folder '{candidates[0]}'",
                )

        # 3. Missing Entity: "Move the file", "Copy the file", "Move file" without target
        if re.search(r"^(?:please\s+)?(?:move|copy)\s+(?:the\s+)?file\s*$", q_lower):
            return AmbiguityResolution(
                is_ambiguous=True,
                ambiguity_type="missing_entity",
                prompt="Which file would you like to move, and where should it go?",
                candidates=[],
            )

        # 4. Missing Entity: "Open the document" / "Open document" without filename
        if re.search(r"^(?:please\s+)?open\s+(?:the\s+)?(?:document|file|pdf)\s*$", q_lower):
            # Check if there are documents in active_directory
            doc_candidates: List[str] = []
            if active_dir.exists() and active_dir.is_dir():
                try:
                    for ext in ("*.pdf", "*.txt", "*.md", "*.docx", "*.csv"):
                        for f in active_dir.glob(ext):
                            if f.is_file():
                                doc_candidates.append(f.name)
                except Exception:
                    pass

            if doc_candidates:
                return AmbiguityResolution(
                    is_ambiguous=True,
                    ambiguity_type="multiple_candidates",
                    prompt="Which document would you like to open?",
                    candidates=doc_candidates[:6],
                    action_template="open file '{choice}'",
                )
            return AmbiguityResolution(
                is_ambiguous=True,
                ambiguity_type="missing_entity",
                prompt="Which document would you like to open?",
                candidates=[],
            )

        # 5. Missing Entity: "Kill process" / "Kill the process" without process name or PID
        if re.search(r"^(?:please\s+)?(?:kill|terminate|stop)\s+(?:the\s+)?process\s*$", q_lower):
            return AmbiguityResolution(
                is_ambiguous=True,
                ambiguity_type="missing_entity",
                prompt="Which process name or PID would you like to terminate?",
                candidates=[],
            )

        return AmbiguityResolution(is_ambiguous=False)
