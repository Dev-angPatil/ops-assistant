"""Unit tests for C-DAC BOSS Linux (Bharat Operating System Solutions) support."""

import unittest
from ops_assistant.collectors.distro_detector import DistroDetector
from ops_assistant.db.distro_db import DistroKnowledgeBase
from ops_assistant.agent.core import ReActAgent


class TestBOSSLinuxSupport(unittest.TestCase):
    def setUp(self):
        self.db = DistroKnowledgeBase(db_path=":memory:")
        self.detector = DistroDetector(db=self.db)

    def test_boss_linux_override_detection(self):
        info = self.detector.detect(override_family="boss")
        self.assertEqual(info.family_id, "debian")
        self.assertEqual(info.distro_id, "boss")
        self.assertIn("BOSS Linux", info.distro_name)
        self.assertEqual(info.package_manager, "apt")
        self.assertEqual(info.init_system, "systemd")
        self.assertEqual(info.default_firewall, "ufw")

    def test_boss_os_release_parsing(self):
        sample_os_release = """
NAME="BOSS Linux"
VERSION="9.0 (Urja)"
ID=boss
ID_LIKE=debian
PRETTY_NAME="BOSS GNU/Linux 9.0 (Urja)"
VERSION_ID="9.0"
HOME_URL="https://bosslinux.in"
"""
        parsed = self.detector.parse_os_release_content(sample_os_release)
        family = self.detector._resolve_family(parsed.get("ID", ""), parsed.get("ID_LIKE", "").split())
        self.assertEqual(family, "debian")

    def test_agent_diagnose_with_boss_distro_override(self):
        agent = ReActAgent(llm_provider=None, distro_db=self.db)
        rep = agent.diagnose("Why is NGINX failing to bind to port 80?", distro_override="boss")
        self.assertEqual(rep.target_subsystem, "nginx")
        self.assertIn("BOSS Linux", rep.reasoning_engine)
        # Verify Debian/BOSS commands are suggested
        cmds = [c.command for c in rep.explanation.proposed_commands]
        self.assertTrue(any("ss " in c or "systemctl" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()
