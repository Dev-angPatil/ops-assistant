"""Unit tests for Modular Distro Knowledge Packs and Lean Distro Seeding."""

import os
import unittest
from pathlib import Path
from ops_assistant.db.distro_db import DistroKnowledgeBase


class TestDistroPacks(unittest.TestCase):
    def setUp(self):
        self.db = DistroKnowledgeBase(db_path=":memory:")

    def tearDown(self):
        self.db.close()

    def test_list_available_and_installed_packs(self):
        avail = self.db.list_available_packs()
        self.assertIn("debian", avail)
        self.assertIn("rhel", avail)
        self.assertIn("arch", avail)
        self.assertIn("alpine", avail)
        self.assertIn("suse", avail)

        installed = self.db.list_installed_packs()
        self.assertTrue(len(installed) >= 1)

    def test_single_distro_lean_seeding(self):
        # Create an isolated in-memory DB seeded ONLY with Arch Linux
        arch_db = DistroKnowledgeBase(db_path=":memory:", target_distro="arch")
        try:
            installed = arch_db.list_installed_packs()
            self.assertEqual(installed, ["arch"])

            # Verify Arch specific commands exist
            cmd = arch_db.get_command("arch", "package", "install", package="htop")
            self.assertIn("pacman -S --needed --noconfirm htop", cmd)

            # Base commands are still accessible via fallback
            base_cmd = arch_db.get_command("arch", "base", "inspect_disk")
            self.assertEqual(base_cmd, "df -h")

            # Debian commands should NOT be present in this lean arch DB
            deb_cmd = arch_db.get_command("debian", "package", "install", package="htop")
            self.assertIsNone(deb_cmd)
        finally:
            arch_db.close()

    def test_pack_add_and_remove(self):
        # Start with only debian
        db = DistroKnowledgeBase(db_path=":memory:", target_distro="debian")
        try:
            self.assertEqual(db.list_installed_packs(), ["debian"])

            # Add RHEL on demand
            added = db.add_pack("rhel")
            self.assertTrue(added)
            self.assertIn("rhel", db.list_installed_packs())
            self.assertIn("debian", db.list_installed_packs())

            # Test RHEL command is now available
            rhel_cmd = db.get_command("rhel", "package", "install", package="nginx")
            self.assertIn("dnf install -y nginx", rhel_cmd)

            # Remove debian
            removed = db.remove_pack("debian")
            self.assertTrue(removed)
            self.assertNotIn("debian", db.list_installed_packs())
            self.assertIn("rhel", db.list_installed_packs())
        finally:
            db.close()

    def test_alias_normalization(self):
        db = DistroKnowledgeBase(db_path=":memory:", target_distro="ubuntu")
        try:
            # "ubuntu" should resolve and seed "debian" pack
            self.assertEqual(db.list_installed_packs(), ["debian"])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
