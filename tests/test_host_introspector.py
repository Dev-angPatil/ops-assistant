"""Unit tests for HostIntrospector runtime capability discovery and command validation."""

import unittest
from ops_assistant.collectors.host_introspector import HostIntrospector, HostRuntimeCapabilities


class TestHostIntrospector(unittest.TestCase):
    def setUp(self):
        self.introspector = HostIntrospector()

    def test_introspect_returns_valid_capabilities(self):
        caps = self.introspector.introspect()
        self.assertIsInstance(caps, HostRuntimeCapabilities)
        self.assertIsNotNone(caps.init_system)
        self.assertIsInstance(caps.is_systemd, bool)
        self.assertIsInstance(caps.is_openrc, bool)
        self.assertIsInstance(caps.is_container, bool)
        self.assertIsInstance(caps.available_package_managers, list)
        self.assertIsInstance(caps.available_firewalls, list)
        self.assertIsInstance(caps.installed_utilities, set)
        self.assertTrue(len(caps.default_shell) > 0)

    def test_has_binary(self):
        # Python3 should always exist in test environment
        self.assertTrue(self.introspector.has_binary("python3") or self.introspector.has_binary("sh"))
        # Non-existent binary should be False
        self.assertFalse(self.introspector.has_binary("non_existent_fake_binary_12345"))

    def test_validate_command_executable(self):
        # Valid commands
        valid, err = self.introspector.validate_command_executable("python3 --version")
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Valid with sudo
        valid, err = self.introspector.validate_command_executable("sudo ls -la")
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Invalid command with missing binary
        valid, err = self.introspector.validate_command_executable("fake_binary_xyz_999 --do-something")
        self.assertFalse(valid)
        self.assertIn("not installed", err)

        # Empty command
        valid, err = self.introspector.validate_command_executable("   ")
        self.assertFalse(valid)
        self.assertEqual(err, "Empty command")


if __name__ == "__main__":
    unittest.main()
