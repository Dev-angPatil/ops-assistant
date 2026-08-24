"""
Compound & Multi-Step Natural Language Intent Chaining Engine for LinuxOpsAssistant.

Provides:
  - ChainStep: Dataclass for individual intent step in a chain.
  - CompoundIntent: Aggregate dataclass holding chained steps, synthesized command,
    reverse rollback, and step-by-step reasoning.
  - CompoundQuerySplitter: Intelligent clause splitter that detects multi-step connectives
    ("and then", "then", "after that", "followed by", "next", "also", "and", ";", "&&", ",")
    while preserving compound noun phrases ("nginx and apache").
  - ChainContext: Context & parameter propagator that resolves pronouns ("in it", "inside it",
    "make it executable", "start it") to paths/entities created or referenced in prior steps.
  - IntentChainEngine: Coordinates multi-step parsing, classification, and compilation into a
    unified CompoundIntent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from ops_assistant.nlp.intent_router import Intent, IntentType, IntentRouter


@dataclass
class ChainStep:
    """Represents a single step within a multi-step compound intent chain."""
    step_number: int
    raw_text: str
    intent: Intent
    command: str
    safety_level: str = "READ_ONLY"
    risk_score: float = 0.05
    rollback_command: Optional[str] = None
    explanation: str = ""
    description: str = ""


@dataclass
class CompoundIntent:
    """Aggregated compound multi-step intent execution plan."""
    raw_query: str
    is_compound: bool = True
    steps: List[ChainStep] = field(default_factory=list)
    chained_command: str = ""
    chained_rollback: Optional[str] = None
    overall_safety_level: str = "READ_ONLY"
    overall_risk_score: float = 0.05
    explanation_steps: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "is_compound": True,
            "total_steps": len(self.steps),
            "command": self.chained_command,
            "rollback_command": self.chained_rollback,
            "safety_level": self.overall_safety_level,
            "risk_score": self.overall_risk_score,
            "summary": self.summary,
            "explanation_steps": self.explanation_steps,
            "steps": [
                {
                    "step_number": s.step_number,
                    "raw_text": s.raw_text,
                    "intent": s.intent.type.value,
                    "command": s.command,
                    "safety_level": s.safety_level,
                    "risk_score": s.risk_score,
                    "rollback_command": s.rollback_command,
                    "explanation": s.explanation,
                    "description": s.description
                }
                for s in self.steps
            ]
        }


class ChainContext:
    """Maintains state and resolves contextual pronouns across multi-step chains."""

    def __init__(self):
        self.last_target_path: Optional[str] = None
        self.last_target_name: Optional[str] = None
        self.last_file_path: Optional[str] = None
        self.last_service: Optional[str] = None
        self.last_package: Optional[str] = None
        self.last_url: Optional[str] = None

    def update_from_step(self, intent: Intent, compiled: Optional[Dict[str, Any]] = None):
        if compiled and isinstance(compiled, dict):
            if compiled.get("path"):
                self.last_target_path = compiled["path"]
                self.last_target_name = compiled["path"].rstrip("/").split("/")[-1]
            if compiled.get("parent") and compiled.get("child"):
                self.last_target_path = f"{compiled['parent']}/{compiled['child']}"
                self.last_target_name = compiled["child"]
            if compiled.get("intent") in ("file_create", "FILE_CREATE") and compiled.get("path"):
                self.last_file_path = compiled["path"]
            if compiled.get("url"):
                self.last_url = compiled["url"]

        args = intent.args or {}
        if args.get("path"):
            self.last_target_path = str(args["path"])
            self.last_target_name = str(args["path"]).rstrip("/").split("/")[-1]
        if args.get("service"):
            self.last_service = str(args["service"])
        if args.get("package"):
            self.last_package = str(args["package"])

    def resolve_clause(self, clause: str) -> str:
        resolved = clause.strip()

        # Replace "in it" / "inside it" / "under it" / "into it" / "inside that folder"
        if self.last_target_path:
            p_target = self.last_target_path
            resolved = re.sub(
                r"\b(?:in|inside|under|into)\s+(?:it|that|that\s+folder|the\s+folder|the\s+dir|the\s+directory)\b",
                f"inside {p_target}",
                resolved,
                flags=re.IGNORECASE
            )

        # Replace "make it executable" / "chmod +x it"
        if self.last_file_path or self.last_target_path:
            f_target = self.last_file_path or self.last_target_path
            resolved = re.sub(
                r"\bmake\s+it\s+(?:executable|runnable)\b",
                f"make {f_target} executable",
                resolved,
                flags=re.IGNORECASE
            )
            resolved = re.sub(
                r"\bchmod\s+\+x\s+it\b",
                f"chmod +x {f_target}",
                resolved,
                flags=re.IGNORECASE
            )

        # Replace "start it" / "stop it" / "restart it"
        if self.last_service:
            s_target = self.last_service
            resolved = re.sub(
                r"\b(start|stop|restart|reload|enable|disable|check)\s+it\b",
                rf"\1 {s_target}",
                resolved,
                flags=re.IGNORECASE
            )

        return resolved


class CompoundQuerySplitter:
    """Intelligently splits compound natural language utterances into distinct sub-clause steps."""

    # Explicit multi-step sequence connectives
    SEQUENCE_DELIMITERS = [
        r"\b(?:and\s+)?then\b",
        r"\bafter\s+that\b",
        r"\bfollowed\s+by\b",
        r"\bnext\b",
        r"\balso\b",
        r"&&",
        r";"
    ]

    VERB_ACTION_WORDS = {
        "create", "make", "touch", "mkdir", "rm", "rmdir", "delete", "remove",
        "clean", "organize", "organise", "move", "transfer", "relocate", "copy",
        "cp", "mv", "chmod", "chown", "install", "uninstall", "update", "upgrade",
        "start", "stop", "restart", "reload", "enable", "disable", "check", "show",
        "list", "inspect", "view", "open", "launch", "download", "fetch", "extract",
        "compress", "tar", "zip", "unzip", "vacuum", "trim", "ping", "audit", "run"
    }

    @classmethod
    def is_compound(cls, text: str) -> bool:
        clean = text.strip()
        if not clean:
            return False

        # Strong sequence indicators always trigger compound detection
        if any(re.search(pat, clean, re.IGNORECASE) for pat in cls.SEQUENCE_DELIMITERS):
            return True

        # Check for clause split on "and" or "," followed by a verb action
        clauses = cls.split_query(clean)
        return len(clauses) >= 2

    @classmethod
    def split_query(cls, text: str) -> List[str]:
        clean = text.strip()
        if not clean:
            return []

        # 1. First split by strong sequence delimiters (then, after that, ;, &&)
        pattern = r"|".join(cls.SEQUENCE_DELIMITERS)
        raw_parts = re.split(pattern, clean, flags=re.IGNORECASE)

        final_clauses: List[str] = []
        for part in raw_parts:
            part_str = part.strip()
            if not part_str:
                continue

            # 2. Check if part contains 'and' or ',' separating distinct action clauses
            sub_clauses = cls._split_and_comma(part_str)
            final_clauses.extend(sub_clauses)

        return [c.strip() for c in final_clauses if c.strip()]

    @classmethod
    def _split_and_comma(cls, text: str) -> List[str]:
        """Splits on 'and' or ',' if the subsequent clause contains an action verb."""
        parts = re.split(r",|\band\b", text, flags=re.IGNORECASE)
        if len(parts) <= 1:
            return [text]

        results: List[str] = []
        curr = parts[0].strip()

        for next_part in parts[1:]:
            next_str = next_part.strip()
            tokens = next_str.lower().split()
            first_words = set(tokens[:3]) if tokens else set()

            # If the next segment starts with or contains an action verb, split!
            if first_words.intersection(cls.VERB_ACTION_WORDS) or re.search(r"^(?:please\s+)?(?:check|show|clean|create|make|start|stop|restart|list|move|copy|open|download|read|write|touch|chmod|chown)\b", next_str, re.IGNORECASE):
                results.append(curr)
                curr = next_str
            else:
                # Compound noun phrase (e.g. "nginx and apache") -> keep together
                curr = f"{curr} and {next_str}"

        results.append(curr)
        return [r for r in results if r]


class IntentChainEngine:
    """Coordinates parsing, parameter propagation, and synthesis of compound intent chains."""

    def __init__(self, router: Optional[IntentRouter] = None):
        self.router = router or IntentRouter()

    def process(self, raw_query: str) -> Union[Intent, CompoundIntent]:
        clean = raw_query.strip()
        if not clean:
            return Intent(IntentType.UNKNOWN, raw=raw_query)

        # Check compound status
        if not CompoundQuerySplitter.is_compound(clean):
            return self.router.classify(clean)

        clauses = CompoundQuerySplitter.split_query(clean)
        if len(clauses) <= 1:
            return self.router.classify(clean)

        context = ChainContext()
        steps: List[ChainStep] = []
        all_commands: List[str] = []
        all_rollbacks: List[str] = []
        explanation_steps: List[str] = []
        max_risk = 0.05
        highest_safety = "READ_ONLY"

        safety_order = {"READ_ONLY": 1, "MODIFYING": 2, "HIGH_RISK": 3, "DESTRUCTIVE": 4}

        for idx, clause in enumerate(clauses, start=1):
            # Resolve pronouns using context from previous steps
            resolved_clause = context.resolve_clause(clause)

            # Classify sub-intent
            intent = self.router.classify(resolved_clause)

            # Compile or determine command representation for step
            cmd_str = ""
            desc_str = ""
            safety_lvl = "READ_ONLY"
            r_score = 0.05
            rollback_cmd = None
            explanation = ""

            from ops_assistant.nlp.nl_compiler import NaturalLanguageCompiler
            nl_compiled = NaturalLanguageCompiler.compile(resolved_clause)

            if nl_compiled and isinstance(nl_compiled, dict):
                cmd_str = nl_compiled.get("command", "")
                desc_str = nl_compiled.get("description", "")
                safety_lvl = nl_compiled.get("safety_level", "MODIFYING")
                r_score = float(nl_compiled.get("risk_score", 0.20))
                rollback_cmd = nl_compiled.get("rollback_command")
                explanation = nl_compiled.get("explanation", desc_str)
                context.update_from_step(intent, compiled=nl_compiled)
            else:
                context.update_from_step(intent)
                cmd_str = self._synthesize_cmd_from_intent(intent, resolved_clause)
                desc_str = f"Execute step {idx}: {intent.type.value}"
                explanation = f"Step {idx}: Execute intent {intent.type.value}"

            if not cmd_str or cmd_str.startswith("#"):
                cmd_str = self._synthesize_cmd_from_intent(intent, resolved_clause)

            if not rollback_cmd:
                rollback_cmd = self._synthesize_rollback(intent, resolved_clause, cmd_str)

            steps.append(ChainStep(
                step_number=idx,
                raw_text=resolved_clause,
                intent=intent,
                command=cmd_str,
                safety_level=safety_lvl,
                risk_score=r_score,
                rollback_command=rollback_cmd,
                explanation=explanation,
                description=desc_str
            ))

            all_commands.append(cmd_str)
            if rollback_cmd:
                all_rollbacks.append(rollback_cmd)

            explanation_steps.append(f"Step {idx}: {explanation or desc_str or cmd_str}")

            if r_score > max_risk:
                max_risk = r_score
            if safety_order.get(safety_lvl, 1) > safety_order.get(highest_safety, 1):
                highest_safety = safety_lvl

        # Combine commands into sequential shell chain
        chained_cmd = " && ".join([c for c in all_commands if c])
        # Combine rollbacks in reverse execution order!
        chained_rollback = "; ".join(reversed([r for r in all_rollbacks if r])) if all_rollbacks else None

        summary_text = f"Multi-step compound execution ({len(steps)} steps): " + " → ".join([s.description or s.command for s in steps])

        return CompoundIntent(
            raw_query=raw_query,
            is_compound=True,
            steps=steps,
            chained_command=chained_cmd,
            chained_rollback=chained_rollback,
            overall_safety_level=highest_safety,
            overall_risk_score=max_risk,
            explanation_steps=explanation_steps,
            summary=summary_text
        )

    def _synthesize_cmd_from_intent(self, intent: Intent, clause: str) -> str:
        it = intent.type
        args = intent.args or {}
        clean_c = clause.strip()

        # Direct shell command strings
        if clean_c.startswith(("touch ", "mkdir ", "rm ", "cp ", "mv ", "chmod ", "chown ", "git ", "systemctl ", "journalctl ", "ufw ", "docker ")):
            return clean_c

        # Handle specific intent types
        if it in (IntentType.FILE_CREATE, IntentType.DIR_CREATE):
            path = args.get("path") or args.get("file") or args.get("name")
            content = args.get("content", "")
            if path:
                if content:
                    return f"echo '{content}' > '{path}'"
                elif it == IntentType.DIR_CREATE or "folder" in clean_c or "dir" in clean_c:
                    return f"mkdir -p '{path}'"
                else:
                    return f"touch '{path}'"

        if it == IntentType.FILE_DELETE:
            path = args.get("path")
            if path:
                return f"rm -f '{path}'"

        if it == IntentType.PERM_CHANGE:
            path = args.get("path")
            mode = args.get("mode", "+x")
            if path:
                return f"chmod {mode} '{path}'"

        if it == IntentType.PROCESS_LIST:
            return "ps aux --sort=-%cpu | head -n 15"
        elif it == IntentType.SYSTEM_CHECK_RAM:
            return "free -h"
        elif it == IntentType.STORAGE_ANALYSE:
            return "df -h"
        elif it == IntentType.STORAGE_CLEAN_TRASH:
            return "gio trash --empty || rm -rf ~/.local/share/Trash/*"
        elif it == IntentType.NETWORK_PORTS:
            return "sudo ss -tulpn"
        elif it == IntentType.SERVICE_START:
            svc = args.get("service", "nginx")
            return f"sudo systemctl start '{svc}'"
        elif it == IntentType.SERVICE_STOP:
            svc = args.get("service", "nginx")
            return f"sudo systemctl stop '{svc}'"
        elif it == IntentType.SERVICE_RESTART:
            svc = args.get("service", "nginx")
            return f"sudo systemctl restart '{svc}'"
        elif it == IntentType.SERVICE_STATUS:
            svc = args.get("service", "nginx")
            return f"systemctl status '{svc}'"
        elif it == IntentType.SYSTEM_INFO:
            return "uname -a ; uptime"
        elif it == IntentType.USER_WHO:
            return "who"
        elif it == IntentType.LOGS_ERRORS:
            return "journalctl -p 3 -xb"

        # General regex extraction fallback
        m_touch = re.search(r"\btouch\s+(['\"]?[a-zA-Z0-9_\-\.\/~]+['\"]?)", clean_c, re.IGNORECASE)
        if m_touch:
            return f"touch {m_touch.group(1)}"

    def _synthesize_rollback(self, intent: Intent, clause: str, cmd_str: str) -> Optional[str]:
        it = intent.type
        args = intent.args or {}
        clean_c = clause.strip()

        if cmd_str.startswith("touch "):
            target = cmd_str[6:].strip().strip("\"'")
            return f"rm -f '{target}'"
        if cmd_str.startswith("mkdir -p "):
            target = cmd_str[9:].strip().strip("\"'")
            return f"rmdir '{target}' 2>/dev/null || rm -rf '{target}'"
        if cmd_str.startswith("sudo systemctl start "):
            svc = cmd_str[21:].strip().strip("\"'")
            return f"sudo systemctl stop '{svc}'"
        if cmd_str.startswith("sudo systemctl stop "):
            svc = cmd_str[20:].strip().strip("\"'")
            return f"sudo systemctl start '{svc}'"

        if it == IntentType.FILE_CREATE:
            path = args.get("path") or args.get("file")
            if path:
                return f"rm -f '{path}'"
        elif it == IntentType.DIR_CREATE:
            path = args.get("path") or args.get("name")
            if path:
                return f"rmdir '{path}' 2>/dev/null || rm -rf '{path}'"
        elif it == IntentType.SERVICE_START:
            svc = args.get("service", "nginx")
            return f"sudo systemctl stop '{svc}'"
        elif it == IntentType.SERVICE_STOP:
            svc = args.get("service", "nginx")
            return f"sudo systemctl start '{svc}'"

        return None
