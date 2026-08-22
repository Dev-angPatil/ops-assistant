"""Multi-turn Conversation Session and Context Memory for Linux Operations Assistant."""

import time
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ConversationTurn:
    """A single query-response turn in an interactive session."""
    query: str
    response_summary: str
    intent: str
    subsystem: Optional[str] = None
    commands: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    symptom: Optional[str] = None
    root_cause: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "response_summary": self.response_summary,
            "intent": self.intent,
            "subsystem": self.subsystem,
            "commands": self.commands,
            "timestamp": self.timestamp,
            "symptom": self.symptom,
            "root_cause": self.root_cause
        }


class ConversationSession:
    """Maintains conversational state, pronoun resolution, and memory across multiple turns."""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.turns: List[ConversationTurn] = []
        self._active_subsystem: Optional[str] = None
        self._last_proposed_commands: List[str] = []

    @property
    def active_subsystem(self) -> Optional[str]:
        return self._active_subsystem

    @property
    def last_turn(self) -> Optional[ConversationTurn]:
        return self.turns[-1] if self.turns else None

    def add_turn(
        self,
        query: str,
        response_summary: str,
        intent: str = "diagnose",
        subsystem: Optional[str] = None,
        commands: Optional[List[str]] = None,
        symptom: Optional[str] = None,
        root_cause: Optional[str] = None
    ) -> ConversationTurn:
        """Record a completed turn into session memory."""
        if subsystem:
            self._active_subsystem = subsystem
        if commands:
            self._last_proposed_commands = list(commands)

        turn = ConversationTurn(
            query=query,
            response_summary=response_summary,
            intent=intent,
            subsystem=subsystem or self._active_subsystem,
            commands=commands or [],
            symptom=symptom,
            root_cause=root_cause
        )
        self.turns.append(turn)
        if len(self.turns) > self.max_history:
            self.turns = self.turns[-self.max_history:]
        return turn

    def resolve_pronouns(self, query: str) -> str:
        """
        Resolves ambiguous conversational references ('it', 'that service', 'the daemon', 'fix it')
        to concrete targets using recent context.
        """
        if not self.turns:
            return query

        last = self.turns[-1]
        resolved = query.strip()

        # Follow-up "fix it" / "apply fix" / "restart it"
        if re.search(r"^(fix\s+it|apply\s+fix|remediate|do\s+it|run\s+the\s+fix)\b", resolved, re.IGNORECASE):
            if last.commands:
                return f"Execute remediation commands: {', '.join(last.commands)}"
            elif last.subsystem:
                return f"Fix and restart service {last.subsystem}"

        # Pronoun substitution for target service
        if last.subsystem:
            svc = last.subsystem
            # e.g., "what about its logs?" -> "what about nginx logs?"
            resolved = re.sub(r"\b(its|that service'?s?|the service'?s?)\s+logs?\b", f"{svc} logs", resolved, flags=re.IGNORECASE)
            # e.g., "why is it failing?" -> "why is nginx failing?"
            resolved = re.sub(r"\b(why\s+is\s+it|why\s+did\s+it|restart\s+it|status\s+of\s+it)\b", lambda m: m.group(0).replace("it", svc), resolved, flags=re.IGNORECASE)
            # e.g., "show me the logs" -> "show me nginx logs" if previously discussing a service
            if re.search(r"^(show\s+me\s+the\s+logs|what\s+do\s+the\s+logs\s+say|check\s+logs?)$", resolved, re.IGNORECASE):
                resolved = f"Show recent system logs for {svc}"

        return resolved

    def get_context_for_llm(self) -> str:
        """Formats the last N turns as context for the LLM prompt."""
        if not self.turns:
            return ""

        lines = ["Previous Conversation Context:"]
        for i, t in enumerate(self.turns[-3:], 1):
            lines.append(f"Turn {i}:")
            lines.append(f"  User Query: {t.query}")
            if t.subsystem:
                lines.append(f"  Target Subsystem: {t.subsystem}")
            if t.root_cause:
                lines.append(f"  Identified Root Cause: {t.root_cause}")
            lines.append(f"  Assistant Summary: {t.response_summary}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Clear session memory."""
        self.turns.clear()
        self._active_subsystem = None
        self._last_proposed_commands.clear()
