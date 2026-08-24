"""
GUI-to-Terminal Fallback Engine and Detector for Linux Ops Assistant.

Provides automated detection of commands requiring real interactive terminals,
sudo password authentication, user prompts, elevated permissions, or manual intervention.
Generates structured fallback payloads with one-click copyable commands, step-by-step
manual execution instructions, prerequisites, expected outputs, and native OS terminal
launch integration.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ops_assistant.config import get_working_dir
from ops_assistant.models import SafetyLevel
from ops_assistant.tools.safety import CommandSafetyValidator


# ---------------------------------------------------------------------------
# Known Interactive TUI, Curses, Pager, and REPL Commands
# ---------------------------------------------------------------------------
INTERACTIVE_TERMINAL_COMMANDS: set[str] = {
    # Text editors & pagers
    "vim", "vi", "nvim", "nano", "emacs", "pico", "less", "more", "most", "view",
    # System monitors & interactive viewers
    "top", "htop", "btop", "atop", "iotop", "iftop", "nethogs", "glances", "gtop",
    "powertop", "tiptop", "vtop", "bmon", "nmon", "iptraf", "iptraf-ng",
    # Terminal multiplexers & shells
    "tmux", "screen", "zellij", "byobu", "bash -i", "zsh -i", "fish", "sh -i",
    "sudo -i", "sudo -s", "su", "su -",
    # Remote shells & container attachments
    "ssh", "sftp", "telnet", "nc", "netcat", "socat",
    # Debuggers & interactive consoles
    "gdb", "lldb", "pdb", "ipdb", "python -i", "python3 -i", "node -i", "irb", "ghci",
    # Disk / partition interactive tools
    "fdisk", "cfdisk", "sfdisk", "gdisk", "cgdisk", "parted",
    # Network & Audio TUIs
    "nmtui", "nmtui-connect", "nmtui-edit", "alsamixer", "pulsemixer", "ncmpcpp",
    # Git & file managers
    "lazygit", "tig", "git-cola", "ranger", "mc", "midnight-commander", "nnn", "lf", "vifm", "fzf",
    # Live streaming / monitoring commands with follow
    "watch", "journalctl -f", "dmesg -w", "tail -f"
}

# Regex patterns indicating interactive input or terminal requirements from stderr/stdout
TTY_ERROR_PATTERNS = [
    r"stdin: is not a tty",
    r"not a tty",
    r"inappropriate ioctl for device",
    r"must be run from a terminal",
    r"TERM environment variable not set",
    r"error opening terminal",
    r"no tty present and no askpass program specified",
    r"sudo: a terminal is required to read the password",
    r"sudo: a password is required",
    r"sudo: 1 incorrect password attempt",
    r"PAM: Authentication failure",
    r"standard input is not a terminal",
    r"terminal required",
]

# Regex patterns indicating user confirmation prompts
INTERACTIVE_PROMPT_PATTERNS = [
    r"\[Y/n\]",
    r"\[y/N\]",
    r"\(yes/no\)\?",
    r"Do you want to continue\?",
    r"Enter passphrase",
    r"Password:",
    r"\[sudo\] password for",
    r"proceed with (?:installation|action|removal)\?",
    r"overwrite [^?]+\? \(y/n\)",
    r"Are you sure you want to continue connecting",
]

# Known Linux desktop terminal emulator binaries in priority order
DESKTOP_TERMINAL_EMULATORS = [
    "x-terminal-emulator",
    "gnome-terminal",
    "kitty",
    "alacritty",
    "konsole",
    "xfce4-terminal",
    "mate-terminal",
    "tilix",
    "foot",
    "wezterm",
    "terminator",
    "urxvt",
    "xterm",
    "ghostty",
    "hyper",
]


from enum import Enum

class FallbackReason(str, Enum):
    """Reason classifications for GUI-to-Terminal fallback."""
    INTERACTIVE_TTY_REQUIRED = "INTERACTIVE_TTY_REQUIRED"
    SUDO_PASSWORD_REQUIRED = "SUDO_PASSWORD_REQUIRED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INTERACTIVE_PROMPT = "INTERACTIVE_PROMPT"
    DESTRUCTIVE_OR_BLOCKED = "DESTRUCTIVE_OR_BLOCKED"
    MANUAL_RUN_REQUESTED = "MANUAL_RUN_REQUESTED"
    FAILED_NEEDS_TERMINAL = "FAILED_NEEDS_TERMINAL"


@dataclass
class TerminalFallbackData:
    """Structured GUI-to-Terminal Fallback Payload."""
    needs_fallback: bool
    reason_code: str
    reason_title: str
    explanation: str

    commands: List[str]
    single_command: str
    multi_command_script: str
    requires_sudo: bool
    is_destructive: bool
    is_high_risk: bool
    safety_level: str
    risk_score: float
    prerequisites: List[str] = field(default_factory=list)
    expected_output: str = ""
    instructions: List[Dict[str, str]] = field(default_factory=list)
    can_launch_terminal: bool = False
    available_terminal: Optional[str] = None
    terminal_launch_supported: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "needs_fallback": self.needs_fallback,
            "reason_code": self.reason_code,
            "reason_title": self.reason_title,
            "explanation": self.explanation,
            "commands": self.commands,
            "single_command": self.single_command,
            "multi_command_script": self.multi_command_script,
            "requires_sudo": self.requires_sudo,
            "is_destructive": self.is_destructive,
            "is_high_risk": self.is_high_risk,
            "safety_level": self.safety_level,
            "risk_score": self.risk_score,
            "prerequisites": self.prerequisites,
            "expected_output": self.expected_output,
            "instructions": self.instructions,
            "can_launch_terminal": self.can_launch_terminal,
            "available_terminal": self.available_terminal,
            "terminal_launch_supported": self.terminal_launch_supported,
        }


class TerminalFallbackDetector:
    """
    Decoupled detector and payload builder for GUI-to-Terminal Fallback.
    Works independently of the command execution engine.
    """

    @classmethod
    def find_available_terminal_emulator(cls) -> Optional[str]:
        """Returns the first available desktop terminal emulator on the host system."""
        for term in DESKTOP_TERMINAL_EMULATORS:
            if shutil.which(term):
                return term
        return None

    @classmethod
    def is_interactive_command(cls, command: str) -> Tuple[bool, str]:
        """Detects if a command inherently requires an interactive terminal/TTY."""
        cmd = command.strip()
        if not cmd:
            return False, ""

        # Split commands chained with |, ;, &&, ||
        sub_cmds = re.split(r"\s*(?:\||;|&&|\|\|)\s*", cmd)
        for sub_cmd in sub_cmds:
            sub = sub_cmd.strip()
            if not sub:
                continue

            # Remove leading sudo and options e.g. "sudo -u user", "sudo -E"
            cleaned_sub = re.sub(r"^sudo\s+(-[a-zA-Z0-9_-]+\s+)*", "", sub).strip()
            tokens = cleaned_sub.split()
            if not tokens:
                continue

            base_cmd = tokens[0]

            # Check full sub-command expressions e.g. "docker exec -it", "docker run -it", "journalctl -f"
            if any(cleaned_sub.startswith(it) or cleaned_sub == it for it in [
                "docker exec -it", "docker run -it", "docker-compose run",
                "podman exec -it", "podman run -it",
                "kubectl exec -it", "journalctl -f", "dmesg -w", "tail -f"
            ]):
                return True, f"Command uses interactive/live streaming mode ({base_cmd})"

            # Check interactive commands list against base_cmd
            if base_cmd in INTERACTIVE_TERMINAL_COMMANDS:
                return True, f"'{base_cmd}' is an interactive terminal application (curses/TUI/pager)"

            # Check interactive flags e.g. `python -i`, `bash -i`, `sh -i`
            if any(flag in tokens for flag in ["-it", "-i"]) and base_cmd in ("docker", "podman", "kubectl", "bash", "zsh", "python", "python3", "node"):
                return True, f"Interactive flag enabled on {base_cmd}"

        return False, ""

    @classmethod
    def detect_fallback_reason(
        cls,
        command: str,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        blocked: bool = False,
        safety_level: Optional[SafetyLevel] = None,
        risk_score: float = 0.0,
        force_fallback: bool = False
    ) -> Optional[FallbackReason]:
        """
        Determines the specific FallbackReason if fallback is needed, or None if successful without fallback.
        """
        is_interactive, _ = cls.is_interactive_command(command)
        combined_output = f"{stdout}\n{stderr}".strip()
        has_sudo_err = bool(re.search(r"\b(sudo: a password is required|sudo: a terminal is required|no tty present and no askpass|PAM: Authentication failure)\b", combined_output, re.IGNORECASE))
        has_perm_err = returncode != 0 and bool(re.search(r"\b(permission denied|operation not permitted|eacces|must be root|are you root\?|cannot open lock file|you cannot perform this operation unless you are root)\b", combined_output, re.IGNORECASE))
        has_prompt = any(re.search(p, combined_output, re.IGNORECASE) for p in INTERACTIVE_PROMPT_PATTERNS)
        has_tty_err = any(re.search(p, combined_output, re.IGNORECASE) for p in TTY_ERROR_PATTERNS)

        if not (blocked or is_interactive or returncode != 0 or has_sudo_err or has_perm_err or has_prompt or has_tty_err or force_fallback or safety_level == SafetyLevel.DESTRUCTIVE):
            return None

        code_str, _, _ = cls.detect_reason(
            command=command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            blocked=blocked,
            safety_level=safety_level,
            risk_score=risk_score
        )
        try:
            return FallbackReason(code_str)
        except ValueError:
            return FallbackReason.FAILED_NEEDS_TERMINAL

    @classmethod
    def detect_reason(
        cls,
        command: str,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        blocked: bool = False,
        safety_level: Optional[SafetyLevel] = None,
        risk_score: float = 0.0
    ) -> Tuple[str, str, str]:
        """
        Determines the specific reason code, title, and user-friendly explanation
        for why terminal fallback is needed.
        """
        combined_output = f"{stdout}\n{stderr}".strip()
        is_interactive, inter_reason = cls.is_interactive_command(command)

        # 1. Blocked by Safety Gate (Destructive commands)
        if blocked or safety_level == SafetyLevel.DESTRUCTIVE:
            return (
                "DESTRUCTIVE_OR_BLOCKED",
                "High-Risk Command Requires Manual Terminal Execution",
                "This command modifies critical system disks or core partitions and has been protected "
                "from automated GUI execution by the safety matrix. You can copy the exact command below "
                "and run it manually in your Linux terminal after verifying the target path."
            )

        # 2. Sudo Password Prompt Requirement in output
        if re.search(r"\b(sudo: a password is required|sudo: a terminal is required|no tty present and no askpass|PAM: Authentication failure|sudo: 1 incorrect password attempt)\b", combined_output, re.IGNORECASE):
            return (
                "SUDO_PASSWORD_REQUIRED",
                "Elevated Sudo Password Authentication Required",
                "This command requires sudo administrative credentials that must be authenticated via a "
                "terminal password prompt. The browser GUI cannot prompt for your sudo password directly. "
                "You can copy the command below and authenticate in your Linux terminal."
            )

        # 3. Permission Denied (without password prompt)
        if returncode != 0 and re.search(r"\b(permission denied|operation not permitted|eacces|must be root|are you root\?|cannot open lock file|you cannot perform this operation unless you are root)\b", combined_output, re.IGNORECASE):
            return (
                "PERMISSION_DENIED",
                "Elevated Privileges Required",
                "Execution was stopped because the command requires elevated system permissions or root privileges. "
                "You can copy the command below and execute it with sudo in your terminal."
            )

        # 4. Interactive Confirmation Prompt in output (e.g. [Y/n], Proceed with...?)
        for pattern in INTERACTIVE_PROMPT_PATTERNS:
            if re.search(pattern, combined_output, re.IGNORECASE):
                return (
                    "INTERACTIVE_PROMPT",
                    "Interactive Confirmation Prompt Detected",
                    "This command paused waiting for interactive confirmation from standard input. "
                    "You can copy the command below and respond to the prompt directly in your terminal."
                )

        # 5. Interactive Terminal / TUI Required (inherent command syntax)
        if is_interactive:
            return (
                "INTERACTIVE_TTY_REQUIRED",
                "Interactive Terminal Required",
                "This command requires a real Linux terminal with interactive TTY and keyboard navigation support "
                "(such as full-screen curses, a text editor, or a process monitor) and cannot run inside a "
                "background browser process. You can copy the command below and run it directly in your terminal."
            )

        # 6. TTY / Terminal Error in output
        for pattern in TTY_ERROR_PATTERNS:
            if re.search(pattern, combined_output, re.IGNORECASE):
                return (
                    "INTERACTIVE_TTY_REQUIRED",
                    "Real TTY Terminal Required",
                    "The operating system reported that a real terminal (TTY) is required for this operation. "
                    "You can copy the command below and execute it seamlessly in your terminal."
                )

        # 7. Generic Non-Zero Exit Code with manual terminal fallback suggestion
        if returncode != 0:
            return (
                "FAILED_NEEDS_TERMINAL",
                "Command Execution Failed — Run in Terminal",
                f"The command exited with return code {returncode}. For real-time debugging, detailed logs, "
                "or interactive troubleshooting, you can run this command directly in your Linux terminal."
            )

        # 8. Default manual execution requested
        return (
            "MANUAL_RUN_REQUESTED",
            "Terminal Execution Available",
            "You can run this command directly in your local terminal for enhanced control or direct shell inspection."
        )

    @classmethod
    def generate_prerequisites(cls, command: str, cwd: Optional[str] = None) -> List[str]:
        """Generates contextual prerequisites for running the command manually."""
        prereqs = []
        active_cwd = cwd or get_working_dir()

        # Working directory prerequisite
        if active_cwd and active_cwd != os.path.expanduser("~") and active_cwd != "/":
            prereqs.append(f"Ensure your terminal is in the project directory: `cd {active_cwd}`")

        # Sudo requirement
        if "sudo " in command or command.startswith("sudo"):
            prereqs.append("Requires `sudo` privileges — have your administrator password ready if prompted")

        # Python venv requirement
        if ".venv" in command or "pip " in command or "python " in command or "pytest" in command:
            if active_cwd and (os.path.exists(os.path.join(active_cwd, ".venv")) or True):
                prereqs.append("Activate the virtual environment if needed: `source .venv/bin/activate`")

        # Docker requirement
        if "docker" in command or "podman" in command:
            prereqs.append("Ensure the Docker daemon is running (`systemctl status docker`)")

        # Git requirement
        if "git " in command:
            prereqs.append("Ensure you are inside a valid git repository")

        # Network requirement
        if any(k in command for k in ["curl ", "wget ", "apt ", "pacman ", "dnf ", "git clone", "pip install", "npm install"]):
            prereqs.append("Requires an active internet connection to download resources")

        if not prereqs:
            prereqs.append("Open your standard Linux terminal emulator")

        return prereqs

    @classmethod
    def generate_expected_output(cls, command: str) -> str:
        """Generates a concise human summary of expected terminal output upon execution."""
        cmd = command.strip()
        tokens = cmd.split()
        base = tokens[0] if tokens else ""
        if base == "sudo" and len(tokens) > 1:
            base = tokens[1]

        if base in ("top", "htop", "btop", "iotop", "glances"):
            return "A full-screen interactive interface displaying live CPU, memory, and running process tables. Press 'q' to exit."
        elif base in ("vim", "vi", "nano", "nvim", "emacs"):
            return "An interactive text editor window with the file loaded for viewing or editing. Save and exit when finished."
        elif base in ("less", "more", "most"):
            return "A scrollable terminal pager displaying the document contents. Press 'q' to exit."
        elif base == "systemctl":
            if any(k in cmd for k in ["restart", "reload", "start", "stop", "enable", "disable"]):
                return "Silent completion with exit code 0 indicating the systemd unit state transition was applied."
            elif "status" in cmd:
                return "Formatted systemd status tree showing active/inactive state, PID, memory, and recent log entries."
        elif any(k in cmd for k in ["pacman", "apt", "apt-get", "dnf", "apk", "zypper"]):
            if any(k in cmd for k in ["install", "remove", "upgrade", "update", "-S", "-R"]):
                return "Package manager transaction summary, download progress bars, and installation confirmation."
        elif base == "docker" or base == "podman":
            if "ps" in cmd:
                return "Table of active container IDs, image names, status, and exposed port mappings."
            elif "run" in cmd or "exec" in cmd:
                return "Interactive terminal shell prompt attached inside the target container."
        elif base == "df":
            return "Filesystem disk space usage table showing mount points, total blocks, and available percentages."
        elif base == "free":
            return "Memory statistics table showing total, used, and free RAM and Swap space."
        elif base == "ss" or base == "netstat":
            return "Table of active listening TCP/UDP sockets, associated PIDs, and local bind addresses."

        return "Command output printed to stdout followed by shell prompt return (Exit Code 0 on success)."

    @classmethod
    def generate_instructions(cls, command: str, cwd: Optional[str] = None) -> List[Dict[str, str]]:
        """Generates step-by-step manual execution instructions for the user."""
        active_cwd = cwd or get_working_dir()
        steps = []

        # Step 1: Open terminal
        steps.append({
            "step": 1,
            "title": "Open Linux Terminal",
            "detail": "Press `Ctrl + Alt + T` or launch your preferred terminal emulator (Kitty, Alacritty, GNOME Terminal, Konsole, etc.) from your application menu."
        })

        # Step 2: Navigate to directory if needed
        if active_cwd and active_cwd != os.path.expanduser("~") and active_cwd != "/":
            steps.append({
                "step": 2,
                "title": "Navigate to Working Directory",
                "detail": f"In your terminal, navigate to the target directory: `cd {active_cwd}`"
            })

        # Step 3: Paste and run
        step_num = len(steps) + 1
        steps.append({
            "step": step_num,
            "title": "Paste & Execute Command",
            "detail": "Click the **Copy Command** button below, paste it into your terminal (`Ctrl + Shift + V` or Right-Click -> Paste), and press `Enter`."
        })

        # Step 4: Sudo authentication if needed
        if "sudo " in command or command.startswith("sudo"):
            step_num = len(steps) + 1
            steps.append({
                "step": step_num,
                "title": "Authenticate with Sudo",
                "detail": "If prompted for your sudo password (`[sudo] password for ...`), type your administrator password and press `Enter` (characters will not appear on screen for security)."
            })

        # Step 5: Verify & Retry in GUI
        step_num = len(steps) + 1
        steps.append({
            "step": step_num,
            "title": "Verify Output & Resume GUI",
            "detail": "Once the command finishes in your terminal, return to this browser window and click **Retry Execution** or continue your workflow."
        })

        return steps

    @classmethod
    def build_fallback_payload(
        cls,
        command_or_commands: Any,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        blocked: bool = False,
        safety_level: Optional[Any] = None,
        risk_score: float = 0.0,
        cwd: Optional[str] = None,
        force_fallback: bool = False
    ) -> TerminalFallbackData:
        """
        Builds a comprehensive, production-ready TerminalFallbackData object.
        Accepts either a single command string or a list of command strings/dicts.
        """
        # Normalize commands list
        commands_list: List[str] = []
        if isinstance(command_or_commands, str):
            cmd_clean = command_or_commands.strip()
            if cmd_clean:
                commands_list = [cmd_clean]
        elif isinstance(command_or_commands, (list, tuple)):
            for item in command_or_commands:
                if isinstance(item, str) and item.strip():
                    commands_list.append(item.strip())
                elif isinstance(item, dict) and item.get("command"):
                    commands_list.append(item["command"].strip())

        primary_cmd = commands_list[0] if commands_list else ""
        all_cmds_script = "\n".join(commands_list)

        # Determine safety levels
        val = CommandSafetyValidator.validate(primary_cmd) if primary_cmd else None
        lvl = safety_level or (val.level if val else SafetyLevel.READ_ONLY)
        lvl_val = lvl.value if hasattr(lvl, "value") else str(lvl)
        r_score = risk_score or (val.risk_score if val else 0.05)
        is_destruct = (lvl_val == SafetyLevel.DESTRUCTIVE.value) or (val.is_destructive if val else False)
        is_hr = (lvl_val == SafetyLevel.HIGH_RISK.value) or (r_score >= 0.65)

        is_inter, _ = cls.is_interactive_command(primary_cmd)
        requires_sudo = any("sudo " in c or c.startswith("sudo") for c in commands_list)

        # Check if fallback is needed
        needs_fb = force_fallback or blocked or (returncode != 0) or is_inter or is_destruct
        if not needs_fb:
            combined = f"{stdout}\n{stderr}"
            if any(re.search(p, combined, re.IGNORECASE) for p in TTY_ERROR_PATTERNS + INTERACTIVE_PROMPT_PATTERNS):
                needs_fb = True

        # Detect reason
        reason_code, reason_title, explanation = cls.detect_reason(
            command=primary_cmd,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            blocked=blocked,
            safety_level=lvl if isinstance(lvl, SafetyLevel) else None,
            risk_score=r_score
        )

        # Prerequisites & expected output
        prereqs = cls.generate_prerequisites(primary_cmd, cwd=cwd)
        expected_out = cls.generate_expected_output(primary_cmd)
        instructions = cls.generate_instructions(primary_cmd, cwd=cwd)

        # Terminal emulator support
        term = cls.find_available_terminal_emulator()
        can_launch = bool(term is not None and ("DISPLAY" in os.environ or "WAYLAND_DISPLAY" in os.environ))

        return TerminalFallbackData(
            needs_fallback=needs_fb,
            reason_code=reason_code,
            reason_title=reason_title,
            explanation=explanation,
            commands=commands_list,
            single_command=primary_cmd,
            multi_command_script=all_cmds_script,
            requires_sudo=requires_sudo,
            is_destructive=is_destruct,
            is_high_risk=is_hr,
            safety_level=lvl_val,
            risk_score=r_score,
            prerequisites=prereqs,
            expected_output=expected_out,
            instructions=instructions,
            can_launch_terminal=can_launch,
            available_terminal=term,
            terminal_launch_supported=can_launch
        )

    @classmethod
    def launch_command_in_desktop_terminal(
        cls,
        command: str,
        cwd: Optional[str] = None,
        hold_open: bool = True
    ) -> Dict[str, Any]:
        """
        Spawns a new native Linux desktop terminal window running the command.
        Uses a bash hold-open wrapper so the user can inspect output and interact.
        """
        term = cls.find_available_terminal_emulator()
        if not term:
            return {
                "success": False,
                "error": "No supported Linux desktop terminal emulator found on this system. Please copy the command to run manually."
            }

        active_cwd = cwd or get_working_dir()
        if not active_cwd or not os.path.exists(active_cwd):
            active_cwd = os.path.expanduser("~")

        cmd_clean = command.strip()
        if not cmd_clean:
            return {"success": False, "error": "Command is empty."}

        # Wrap command so the terminal stays open and returns to an interactive bash shell
        if hold_open:
            shell_script = f"cd {shlex.quote(active_cwd)} && echo -e '\\033[1;36m[AI Copilot Terminal Session]\\033[0m Running: {shlex.quote(cmd_clean)}\\n' && {cmd_clean}; echo -e '\\n\\033[1;32m[Command Finished]\\033[0m Press Enter or continue working in this shell...'; exec bash"
        else:
            shell_script = f"cd {shlex.quote(active_cwd)} && {cmd_clean}"

        try:
            # Build terminal-specific argument invocation
            if term in ("gnome-terminal", "mate-terminal", "tilix", "xfce4-terminal", "terminator", "x-terminal-emulator"):
                args = [term, "--working-directory", active_cwd, "--", "bash", "-c", shell_script]
            elif term in ("kitty", "foot", "wezterm", "ghostty"):
                args = [term, "--directory", active_cwd, "bash", "-c", shell_script]
            elif term in ("alacritty",):
                args = [term, "--working-directory", active_cwd, "-e", "bash", "-c", shell_script]
            elif term in ("konsole",):
                args = [term, "--workdir", active_cwd, "-e", "bash", "-c", shell_script]
            elif term in ("xterm", "urxvt"):
                args = [term, "-e", "bash", "-c", shell_script]
            else:
                args = [term, "-e", "bash", "-c", shell_script]

            proc = subprocess.Popen(
                args,
                cwd=active_cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            return {
                "success": True,
                "message": f"Spawned terminal '{term}' (PID {proc.pid}) running command.",
                "terminal": term,
                "pid": proc.pid,
                "command": cmd_clean
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to spawn terminal emulator '{term}': {str(e)}"
            }
