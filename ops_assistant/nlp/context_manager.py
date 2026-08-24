"""
Conversational Context Manager and Multi-Turn Memory for LinuxOpsAssistant.

Maintains conversation history, active directory contexts, recent entities,
and performs anaphora resolution for natural multi-turn follow-ups.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ConversationTurn:
    """Represents a single query-action turn in the conversation."""
    query: str
    intent: str
    command: Optional[str]
    target_path: Optional[str] = None
    service_name: Optional[str] = None
    process_name: Optional[str] = None
    output_summary: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class ContextManager:
    """Manages multi-turn conversational state and resolves contextual follow-ups."""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.active_directory: str = os.getcwd()
        self.last_target_file: Optional[str] = None
        self.last_target_folder: Optional[str] = None
        self.last_service: Optional[str] = None
        self.last_process: Optional[str] = None
        self.last_command: Optional[str] = None
        self.turns: List[ConversationTurn] = []

    def update_context(
        self,
        query: str,
        intent: str,
        command: Optional[str] = None,
        target_path: Optional[str] = None,
        service_name: Optional[str] = None,
        process_name: Optional[str] = None,
        output_summary: Optional[str] = None,
    ):
        """Records a new conversation turn and updates state trackers."""
        if target_path:
            expanded = os.path.expanduser(target_path)
            if os.path.isdir(expanded):
                self.active_directory = expanded
                self.last_target_folder = expanded
            else:
                self.last_target_file = expanded
                parent = os.path.dirname(expanded)
                if parent and os.path.isdir(parent):
                    self.active_directory = parent

        if service_name:
            self.last_service = service_name
        if process_name:
            self.last_process = process_name
        if command:
            self.last_command = command

        turn = ConversationTurn(
            query=query,
            intent=intent,
            command=command,
            target_path=target_path,
            service_name=service_name,
            process_name=process_name,
            output_summary=output_summary,
        )
        self.turns.append(turn)
        if len(self.turns) > self.max_history:
            self.turns.pop(0)

    def resolve_contextual_query(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Resolves anaphora and contextual references (e.g. 'largest file', 'restart it', 'its status').

        Returns:
            (resolved_query: str, context_metadata: Dict[str, Any])
        """
        q = query.strip()
        q_lower = q.lower()
        context_meta: Dict[str, Any] = {
            "active_directory": self.active_directory,
            "last_service": self.last_service,
            "last_process": self.last_process,
            "last_target_file": self.last_target_file,
            "last_target_folder": self.last_target_folder,
            "resolved_from_context": False,
        }

        # 1. Follow-up: "Delete the largest file" / "find largest file" in previously opened folder
        if re.search(r"\b(?:largest|biggest)\s+file\b", q_lower):
            target_dir = self.active_directory
            if target_dir and os.path.isdir(target_dir):
                context_meta["resolved_from_context"] = True
                context_meta["target_directory"] = target_dir
                # If command is delete largest file
                if any(verb in q_lower for verb in ("delete", "remove", "erase", "trash")):
                    resolved = f"delete the largest file in '{target_dir}'"
                    return resolved, context_meta
                else:
                    resolved = f"find the largest file in '{target_dir}'"
                    return resolved, context_meta

        # 2. Follow-up: "restart it" / "stop it" / "its status" / "check its logs" referring to last service
        if self.last_service and re.search(r"\b(?:it|its|that\s+service|the\s+service)\b", q_lower):
            svc = self.last_service
            context_meta["resolved_from_context"] = True
            if "restart" in q_lower:
                return f"restart {svc}", context_meta
            elif "stop" in q_lower:
                return f"stop {svc}", context_meta
            elif "status" in q_lower:
                return f"status of {svc}", context_meta
            elif "log" in q_lower:
                return f"logs of {svc}", context_meta

        # 3. Follow-up: "kill it" / "terminate it" referring to last process
        if self.last_process and re.search(r"\b(?:kill|terminate|stop)\s+(?:it|that\s+process|the\s+process)\b", q_lower):
            context_meta["resolved_from_context"] = True
            return f"kill process {self.last_process}", context_meta

        # 4. Follow-up: "open it" referring to last file or folder
        if (self.last_target_file or self.last_target_folder) and re.search(r"\bopen\s+(?:it|that\s+file|that\s+folder)\b", q_lower):
            target = self.last_target_file or self.last_target_folder
            context_meta["resolved_from_context"] = True
            return f"open '{target}'", context_meta

        return q, context_meta

    def get_summary(self) -> str:
        """Returns readable debug summary of active memory context."""
        return (
            f"Active Dir: {self.active_directory} | "
            f"Last Svc: {self.last_service} | "
            f"Last Proc: {self.last_process} | "
            f"History: {len(self.turns)} turns"
        )
