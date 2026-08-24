"""
Tests for GUI-to-Terminal Fallback Feature.
Covers:
- TerminalFallbackDetector classification matrix (TTY, sudo, permissions, prompts, destructive, manual)
- Fallback payload construction (prerequisites, step-by-step instructions, expected outputs, scripts)
- Native terminal emulator detection & launcher
- Integration with ExecutionOutcomeExplainer and Agent Core
- REST API integration with terminal fallback payloads
"""

import unittest
from unittest.mock import patch, MagicMock

from ops_assistant.tools.terminal_fallback import (
    TerminalFallbackDetector,
    TerminalFallbackData,
    FallbackReason,
)
from ops_assistant.tools.safety import SafetyLevel, CommandSafetyValidator
from ops_assistant.explainer.xai import ExecutionOutcomeExplainer
from ops_assistant.agent.core import ReActAgent


class TestTerminalFallbackDetector(unittest.TestCase):

    def test_detect_interactive_tui_commands(self):
        """Interactive commands (htop, vim, nano, less, tmux, ssh, etc.) should be detected."""
        interactive_cmds = [
            "htop",
            "top -b",
            "vim /etc/hosts",
            "nano ~/.bashrc",
            "less /var/log/syslog",
            "more /var/log/messages",
            "fzf --preview 'cat {}'",
            "tmux new-session -s ops",
            "ssh user@remotehost",
            "docker run -it ubuntu:latest bash",
            "docker exec -it my_container sh",
            "kubectl exec -it pod-123 -- /bin/bash",
            "gdb ./my_binary",
            "watch -n 1 nvidia-smi",
            "journalctl -f -u nginx",
            "nmtui",
            "alsamixer",
            "cfdisk /dev/sda",
        ]
        for cmd in interactive_cmds:
            reason = TerminalFallbackDetector.detect_fallback_reason(command=cmd)
            self.assertEqual(reason, FallbackReason.INTERACTIVE_TTY_REQUIRED, f"Failed for cmd: {cmd}")

    def test_detect_tty_error_outputs(self):
        """Errors indicating missing TTY / stdin / terminal should be classified as INTERACTIVE_TTY_REQUIRED."""
        test_cases = [
            ("some_tool", 1, "", "stdin: is not a tty"),
            ("docker run app", 1, "", "the input device is not a TTY"),
            ("custom_tool", 25, "", "inappropriate ioctl for device"),
            ("ncurses_app", 1, "", "TERM environment variable not set."),
            ("cli_tool", 1, "", "must be run from a terminal"),
        ]
        for cmd, rc, stdout, stderr in test_cases:
            reason = TerminalFallbackDetector.detect_fallback_reason(
                command=cmd, returncode=rc, stdout=stdout, stderr=stderr
            )
            self.assertEqual(reason, FallbackReason.INTERACTIVE_TTY_REQUIRED)

    def test_detect_sudo_password_prompts(self):
        """Sudo password requirement failures must be classified as SUDO_PASSWORD_REQUIRED."""
        test_cases = [
            ("sudo systemctl restart nginx", 1, "", "sudo: a password is required"),
            ("sudo apt update", 1, "", "sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper"),
            ("sudo pacman -Syu", 1, "", "sudo: no tty present and no askpass program specified"),
            ("sudo dnf upgrade", 1, "", "sudo: PAM: Authentication failure"),
        ]
        for cmd, rc, stdout, stderr in test_cases:
            reason = TerminalFallbackDetector.detect_fallback_reason(
                command=cmd, returncode=rc, stdout=stdout, stderr=stderr
            )
            self.assertEqual(reason, FallbackReason.SUDO_PASSWORD_REQUIRED)

    def test_detect_permission_denied(self):
        """Permission denied outputs without sudo password prompt should be PERMISSION_DENIED."""
        test_cases = [
            ("cat /etc/shadow", 1, "", "cat: /etc/shadow: Permission denied"),
            ("rm /root/secret.txt", 1, "", "rm: cannot remove '/root/secret.txt': Operation not permitted"),
            ("apt update", 100, "", "E: Could not open lock file - open (13: Permission denied)\nE: Are you root?"),
            ("pacman -S vim", 1, "", "error: you cannot perform this operation unless you are root."),
        ]
        for cmd, rc, stdout, stderr in test_cases:
            reason = TerminalFallbackDetector.detect_fallback_reason(
                command=cmd, returncode=rc, stdout=stdout, stderr=stderr
            )
            self.assertEqual(reason, FallbackReason.PERMISSION_DENIED)

    def test_detect_interactive_prompts(self):
        """Interactive confirmation prompts ([y/N], (yes/no)?) must be INTERACTIVE_PROMPT."""
        test_cases = [
            ("apt-get install pkg", 1, "Do you want to continue? [Y/n] ", ""),
            ("pacman -S pkg", 0, "Proceed with installation? [Y/n]", ""),
            ("ssh host", 255, "Are you sure you want to continue connecting (yes/no/[fingerprint])?", ""),
        ]
        for cmd, rc, stdout, stderr in test_cases:
            reason = TerminalFallbackDetector.detect_fallback_reason(
                command=cmd, returncode=rc, stdout=stdout, stderr=stderr
            )
            self.assertEqual(reason, FallbackReason.INTERACTIVE_PROMPT)

    def test_detect_destructive_blocked_commands(self):
        """Destructive / blocked commands must be classified as DESTRUCTIVE_OR_BLOCKED."""
        reason = TerminalFallbackDetector.detect_fallback_reason(
            command="mkfs.ext4 /dev/sda1",
            blocked=True,
            safety_level=SafetyLevel.DESTRUCTIVE
        )
        self.assertEqual(reason, FallbackReason.DESTRUCTIVE_OR_BLOCKED)

    def test_successful_non_interactive_no_fallback(self):
        """Standard successful commands should return None (needs_fallback=False)."""
        reason = TerminalFallbackDetector.detect_fallback_reason(
            command="ls -la",
            returncode=0,
            stdout="total 12\ndrwxr-xr-x 2 user user 4096 ...",
            stderr=""
        )
        self.assertIsNone(reason)


class TestFallbackPayloadBuilder(unittest.TestCase):

    def test_build_payload_for_interactive_command(self):
        payload = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands="htop",
            cwd="/home/god/Projects/edi2"
        )
        self.assertTrue(payload.needs_fallback)
        self.assertEqual(payload.reason_code, "INTERACTIVE_TTY_REQUIRED")
        self.assertIn("Interactive Terminal Required", payload.reason_title)
        self.assertIn("interactive TTY", payload.explanation)
        self.assertEqual(payload.single_command, "htop")
        self.assertFalse(payload.requires_sudo)
        self.assertGreaterEqual(len(payload.instructions), 3)
        self.assertNotEqual(payload.expected_output, "")

    def test_build_payload_for_sudo_command(self):
        payload = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands="sudo systemctl restart nginx",
            returncode=1,
            stderr="sudo: a password is required",
            cwd="/var/www"
        )
        self.assertTrue(payload.needs_fallback)
        self.assertEqual(payload.reason_code, "SUDO_PASSWORD_REQUIRED")
        self.assertTrue(payload.requires_sudo)
        self.assertTrue(any("sudo password" in inst["detail"].lower() for inst in payload.instructions))
        self.assertTrue(any("cd /var/www" in p for p in payload.prerequisites))

    def test_build_payload_for_multi_commands(self):
        cmds = [
            "git checkout main",
            "git pull origin main",
            "npm install",
            "npm run build"
        ]
        payload = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands=cmds,
            returncode=1,
            stderr="npm ERR! code ENOENT",
            cwd="/home/god/Projects/app"
        )
        self.assertTrue(payload.needs_fallback)
        self.assertEqual(len(payload.commands), 4)
        self.assertEqual(payload.multi_command_script, "git checkout main\ngit pull origin main\nnpm install\nnpm run build")
        self.assertEqual(payload.to_dict()["multi_command_script"], payload.multi_command_script)

    def test_prerequisites_generation_docker_and_venv(self):
        prereqs_docker = TerminalFallbackDetector.generate_prerequisites(
            "docker-compose up -d",
            cwd="/app"
        )
        self.assertTrue(any("Docker daemon" in p for p in prereqs_docker))
        self.assertTrue(any("cd /app" in p for p in prereqs_docker))

        prereqs_python = TerminalFallbackDetector.generate_prerequisites(
            "pytest tests/",
            cwd="/home/god/Projects/edi2"
        )
        self.assertTrue(any("virtual environment" in p.lower() or "cd /home/god/Projects/edi2" in p for p in prereqs_python))


class TestNativeTerminalLauncher(unittest.TestCase):

    def test_find_available_terminal_emulator(self):
        """Should detect at least one terminal emulator or fallback gracefully."""
        term = TerminalFallbackDetector.find_available_terminal_emulator()
        self.assertTrue(term is None or isinstance(term, str))

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_launch_command_in_desktop_terminal_success(self, mock_popen, mock_which):
        mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd == "x-terminal-emulator" else None
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        res = TerminalFallbackDetector.launch_command_in_desktop_terminal(
            command="echo 'Testing fallback'",
            cwd="/tmp",
            hold_open=True
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["pid"], 9999)
        self.assertEqual(res["terminal"], "x-terminal-emulator")
        mock_popen.assert_called_once()


class TestExplainerAndAgentIntegration(unittest.TestCase):

    def test_xai_explainer_includes_terminal_fallback(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="sudo systemctl restart nginx",
            returncode=1,
            stdout="",
            stderr="sudo: a password is required",
            query="restart web server"
        )
        self.assertIn("terminal_fallback", outcome)
        fb = outcome["terminal_fallback"]
        self.assertTrue(fb["needs_fallback"])
        self.assertEqual(fb["reason_code"], "SUDO_PASSWORD_REQUIRED")

    def test_agent_core_attaches_terminal_fallback(self):
        agent = ReActAgent(llm_provider=None)
        res = agent.execute_agent_action("show interactive htop", execute=False)
        self.assertIn("terminal_fallback", res)
        fb = res["terminal_fallback"]
        self.assertIsNotNone(fb)
        self.assertTrue("commands" in fb or "single_command" in fb)


class TestServerTerminalFallbackAPI(unittest.TestCase):

    def test_fallback_payload_endpoint_resolution(self):
        payload = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands="vim /etc/fstab",
            cwd="/home/god"
        )
        data = payload.to_dict()
        self.assertTrue(data["needs_fallback"])
        self.assertEqual(data["reason_code"], "INTERACTIVE_TTY_REQUIRED")
        self.assertEqual(data["single_command"], "vim /etc/fstab")
        self.assertGreater(len(data["instructions"]), 0)

    def test_execute_blocked_command_returns_terminal_fallback(self):
        cmd = "mkfs.ext4 /dev/sda"
        val = CommandSafetyValidator.validate(cmd)
        self.assertEqual(val.level, SafetyLevel.DESTRUCTIVE)

        fallback = TerminalFallbackDetector.build_fallback_payload(
            command_or_commands=cmd,
            returncode=1,
            stderr=f"DESTRUCTIVE command blocked: {val.matched_rule}",
            blocked=True,
            safety_level=val.level,
            risk_score=val.risk_score
        )
        fb_dict = fallback.to_dict()
        self.assertTrue(fb_dict["needs_fallback"])
        self.assertEqual(fb_dict["reason_code"], "DESTRUCTIVE_OR_BLOCKED")
        self.assertTrue(fb_dict["is_destructive"])


if __name__ == "__main__":
    unittest.main()
