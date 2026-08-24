"""Unit tests for Self-Correction & Reflection Loop (stderr error recovery) engine."""

import os
import unittest
from unittest.mock import MagicMock

from ops_assistant.explainer.self_correction import SelfCorrectionEngine, ReflectionRecord
from ops_assistant.tools.executor import SafeExecutor
from ops_assistant.models import SafetyLevel


class TestSelfCorrectionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SelfCorrectionEngine()
        self.executor = SafeExecutor()

    def test_permission_denied_reflection(self):
        rec = self.engine.reflect(
            command="touch /etc/protected.conf",
            returncode=126,
            stderr="touch: cannot touch '/etc/protected.conf': Permission denied"
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "PREPEND_SUDO")
        self.assertEqual(rec.corrected_command, "sudo touch /etc/protected.conf")
        self.assertIn("PERMISSION_DENIED", rec.reflection)

    def test_command_not_found_legacy_mapping(self):
        rec = self.engine.reflect(
            command="open https://google.com",
            returncode=127,
            stderr="open: command not found"
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "MAP_LEGACY_COMMAND")
        self.assertEqual(rec.corrected_command, "xdg-open https://google.com")

    def test_lock_conflict_reflection(self):
        rec = self.engine.reflect(
            command="sudo pacman -S nginx",
            returncode=1,
            stderr="error: failed to init transaction (unable to lock database)\nerror: could not lock database: File exists\n  if you're sure a package manager is not already\n  running, you can remove /var/lib/pacman/db.lck"
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "REMOVE_STALE_LOCK")
        self.assertEqual(rec.prerequisite_command, "sudo rm -f /var/lib/pacman/db.lck")
        self.assertEqual(rec.corrected_command, "sudo pacman -S nginx")

    def test_missing_directory_reflection(self):
        rec = self.engine.reflect(
            command="touch /tmp/nonexistent_parent_dir_9999/test.txt",
            returncode=1,
            stderr="touch: cannot touch '/tmp/nonexistent_parent_dir_9999/test.txt': No such file or directory"
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "CREATE_PARENT_DIRECTORY")
        self.assertEqual(rec.prerequisite_command, "mkdir -p /tmp/nonexistent_parent_dir_9999")

    def test_unsupported_flag_reflection(self):
        rec = self.engine.reflect(
            command="grep --invalidflag foo /etc/hosts",
            returncode=2,
            stderr="grep: unrecognized option '--invalidflag'\nUsage: grep [OPTION]... PATTERNS [FILE]..."
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "STRIP_UNSUPPORTED_FLAG")
        self.assertEqual(rec.corrected_command, "grep foo /etc/hosts")

    def test_execute_with_reflection_successful_recovery(self):
        # Mock executor where first command fails (command not found) and corrected command succeeds
        mock_executor = MagicMock()
        mock_executor.execute.side_effect = [
            {
                "command": "open https://example.com",
                "executed": True,
                "returncode": 127,
                "stdout": "",
                "stderr": "open: command not found",
                "elapsed_ms": 1.0
            },
            {
                "command": "xdg-open https://example.com",
                "executed": True,
                "returncode": 0,
                "stdout": "[Desktop GUI Launched]",
                "stderr": "",
                "elapsed_ms": 1.0
            }
        ]

        res = self.engine.execute_with_reflection(
            executor=mock_executor,
            command_str="open https://example.com",
            max_retries=3
        )
        self.assertTrue(res.get("self_corrected"))
        self.assertEqual(res.get("attempts"), 2)
        self.assertEqual(res.get("original_command"), "open https://example.com")
        self.assertEqual(res.get("final_command"), "xdg-open https://example.com")

    def test_max_retries_termination(self):
        # Mock executor where command repeatedly fails with unrecoverable error
        mock_executor = MagicMock()
        mock_executor.execute.return_value = {
            "command": "unknown_tool",
            "executed": True,
            "returncode": 1,
            "stdout": "",
            "stderr": "fatal: unrecoverable hardware fault",
            "elapsed_ms": 1.0
        }

        res = self.engine.execute_with_reflection(
            executor=mock_executor,
            command_str="unknown_tool",
            max_retries=2
        )
        self.assertFalse(res.get("self_corrected"))
        self.assertGreaterEqual(len(res.get("reflection_trace", [])), 1)

    def test_llm_reflection_fallback(self):
        mock_llm = MagicMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate.return_value = '{"reflection": "Invalid argument format", "corrected_command": "echo fixed", "can_recover": true}'

        rec = self.engine.reflect(
            command="some_complex_tool --bad-arg",
            returncode=1,
            stderr="Unknown complex failure trace",
            llm_provider=mock_llm
        )
        self.assertTrue(rec.can_recover)
        self.assertEqual(rec.suggested_action, "LLM_PROPOSED_FIX")
        self.assertEqual(rec.corrected_command, "echo fixed")


if __name__ == "__main__":
    unittest.main()
