"""Unit tests for InstallTracker and phased background installation state."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from ops_assistant.config import (
    ConfigManager,
    get_config,
    get_install_phase,
    set_install_phase,
    is_fully_installed,
    finalize_enhancement,
)
from ops_assistant.install_tracker import InstallTracker, is_pid_alive


class TestInstallTracker(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmpdir.name)
        self.config_file = self.tmp_path / "config.json"
        self.state_file = self.tmp_path / "enhance.state.json"
        self.cfg_mgr = ConfigManager(config_file=self.config_file)
        self.tracker = InstallTracker(state_file=self.state_file, config_manager=self.cfg_mgr)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_pid_liveness(self):
        """Verify is_pid_alive accurately identifies active vs inactive PIDs."""
        self.assertTrue(is_pid_alive(os.getpid()))
        # Test PID 0 or negative
        self.assertFalse(is_pid_alive(None))
        self.assertFalse(is_pid_alive(0))
        self.assertFalse(is_pid_alive(-1))
        # Arbitrary high PID that does not exist
        self.assertFalse(is_pid_alive(99999999))

    def test_default_tracker_status(self):
        """Verify default tracker state when no state file exists."""
        st = self.tracker.get_status()
        self.assertEqual(st["phase"], "complete")
        self.assertEqual(st["status"], "completed")
        self.assertEqual(st["progress_pct"], 100.0)
        self.assertTrue(self.tracker.is_complete())
        self.assertFalse(self.tracker.is_enhancing())

    def test_tracker_lifecycle(self):
        """Verify mark_start -> mark_step -> mark_complete transitions."""
        current_pid = os.getpid()

        # 1. Start enhancement
        st = self.tracker.mark_start(model_key="qwen2.5-coder-0.5b", pid=current_pid, total_steps=3)
        self.assertEqual(st["phase"], "enhancing")
        self.assertEqual(st["status"], "running")
        self.assertEqual(st["pid"], current_pid)
        self.assertTrue(self.tracker.is_enhancing())
        self.assertFalse(self.tracker.is_complete())

        # 2. Update step
        st2 = self.tracker.mark_step(2, 3, "Downloading model weights...", status="downloading", progress_pct=45.5)
        self.assertEqual(st2["current_step"], 2)
        self.assertEqual(st2["status"], "downloading")
        self.assertEqual(st2["progress_pct"], 45.5)
        self.assertEqual(self.tracker.get_model_progress(), 45.5)

        # 3. Mark complete
        st3 = self.tracker.mark_complete(model_key="qwen2.5-coder-0.5b", model_path="/fake/path.gguf", provider="gguf")
        self.assertEqual(st3["phase"], "complete")
        self.assertEqual(st3["status"], "completed")
        self.assertEqual(st3["progress_pct"], 100.0)
        self.assertTrue(self.tracker.is_complete())
        self.assertFalse(self.tracker.is_enhancing())

    def test_tracker_stale_pid_detection(self):
        """Verify dead PID is flagged as interrupted rather than indefinitely running."""
        dead_pid = 99999999  # Guaranteed inactive

        self.tracker.mark_start(model_key="qwen2.5-coder-0.5b", pid=dead_pid, total_steps=3)
        self.tracker.mark_step(2, 3, "Downloading...", status="downloading", progress_pct=25.0)

        status = self.tracker.get_status()
        self.assertFalse(status["is_alive"])
        self.assertEqual(status["status"], "interrupted")
        self.assertFalse(self.tracker.is_enhancing())

    def test_tracker_mark_failed(self):
        """Verify failure state recording."""
        self.tracker.mark_start(model_key="qwen2.5-coder-0.5b")
        st = self.tracker.mark_failed("Network connection timed out.")
        self.assertEqual(st["status"], "failed")
        self.assertIn("timed out", st["error"])

    def test_config_phased_install_helpers(self):
        """Verify config helper methods for phased installation."""
        # Initial phase
        self.assertEqual(self.cfg_mgr.get_install_phase(), "complete")

        # Transition to core_only
        self.cfg_mgr.set_install_phase("core_only", pending_model_key="llama-3.2-3b")
        self.assertEqual(self.cfg_mgr.get_install_phase(), "core_only")
        self.assertEqual(self.cfg_mgr.get("pending_model_key"), "llama-3.2-3b")
        self.assertFalse(self.cfg_mgr.is_fully_installed())

        # Finalize enhancement
        res = self.cfg_mgr.finalize_enhancement(
            model_key="llama-3.2-3b",
            model_path="/path/to/llama.gguf",
            hardware_tier="Tier-2-Balanced",
            threads=4,
            ctx_size=2048,
            gpu_layers=0,
            provider="gguf"
        )
        self.assertEqual(res["install_phase"], "complete")
        self.assertTrue(res["setup_completed"])
        self.assertEqual(res["active_model_key"], "llama-3.2-3b")
        self.assertIsNone(res["pending_model_key"])
        self.assertTrue(self.cfg_mgr.is_fully_installed())


if __name__ == "__main__":
    unittest.main()
