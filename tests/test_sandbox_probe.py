"""Unit tests for Ephemeral Sandbox Probe."""

import unittest
from ops_assistant.tools.sandbox_probe import EphemeralSandboxProbe

class TestEphemeralSandboxProbe(unittest.TestCase):
    def setUp(self):
        self.probe = EphemeralSandboxProbe(timeout_seconds=2.0)

    def test_read_only_command_verification(self):
        res = self.probe.verify_command("ps aux | grep nginx")
        self.assertTrue(res.is_verified)
        self.assertEqual(res.exit_code, 0)
        self.assertEqual(res.isolation_mode, "READ_ONLY_INSPECTION")

    def test_valid_syntax_command_verification(self):
        res = self.probe.verify_command("systemctl restart nginx")
        self.assertTrue(res.is_verified)
        self.assertIn(res.isolation_mode, ["UNSHARE_ROOTLESS_NAMESPACE", "POSIX_SYNTAX_VALIDATOR"])

    def test_invalid_syntax_command(self):
        res = self.probe.verify_command("if [ -f /tmp/test ; then echo err")
        self.assertFalse(res.is_verified)
        self.assertNotEqual(res.exit_code, 0)
        self.assertEqual(res.isolation_mode, "POSIX_SYNTAX_VALIDATOR")

    def test_empty_command(self):
        res = self.probe.verify_command("   ")
        self.assertFalse(res.is_verified)
        self.assertEqual(res.isolation_mode, "INPUT_VALIDATION")

    def test_sandbox_result_to_dict(self):
        res = self.probe.verify_command("df -h")
        d = res.to_dict()
        self.assertIsInstance(d, dict)
        self.assertIn("isolation_mode", d)
        self.assertIn("is_verified", d)
        self.assertIn("latency_ms", d)


if __name__ == "__main__":
    unittest.main()

