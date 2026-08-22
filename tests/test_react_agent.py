"""Unit tests for ReAct Autonomous Agent & Tools Registry Subsystem."""

import unittest
from unittest.mock import MagicMock

from ops_assistant.agent.tools_registry import AgentToolsRegistry, AgentTool
from ops_assistant.agent.core import ReActAgent
from ops_assistant.agent.providers import LLMProvider, GeminiProvider, OllamaProvider, LlamaCppProvider
from ops_assistant.models import SafetyLevel, LogRecord


class TestReActAgentAndToolsRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = AgentToolsRegistry()
        self.agent = ReActAgent(llm_provider=None)

    def test_tools_registry_contains_core_inspection_tools(self):
        schemas = self.registry.get_schemas()
        tool_names = {s["name"] for s in schemas}

        expected_tools = {
            "inspect_system_health",
            "inspect_service",
            "inspect_listening_ports",
            "query_system_logs",
            "inspect_disk_and_inodes",
            "inspect_processes",
            "run_read_only_command",
            "explain_command_flags",
            "verify_command_safety"
        }
        for t in expected_tools:
            self.assertIn(t, tool_names, f"Missing tool in registry: {t}")

    def test_inspect_system_health_live_execution(self):
        res = self.registry.execute("inspect_system_health", {})
        self.assertEqual(res["status"], "success")
        data = res["result"]
        self.assertIn("hostname", data)
        self.assertIn("kernel", data)
        self.assertIn("pressure_status", data)

    def test_inspect_listening_ports_execution(self):
        res = self.registry.execute("inspect_listening_ports", {"port": 22})
        self.assertEqual(res["status"], "success")
        self.assertIn("total_listening", res["result"])

    def test_read_only_command_safety_enforcement(self):
        # Read only command allowed
        res_ok = self.registry.execute("run_read_only_command", {"command": "ss -tulpn"})
        self.assertEqual(res_ok["status"], "success")
        self.assertIn("command", res_ok["result"])

        # Modifying / Destructive command blocked by observation tool
        res_blocked = self.registry.execute("run_read_only_command", {"command": "rm -rf /"})
        self.assertEqual(res_blocked["status"], "success")
        self.assertTrue(res_blocked["result"].get("blocked"))

    def test_verify_command_safety_tool(self):
        res = self.registry.execute("verify_command_safety", {"command": "sudo ufw allow 443/tcp"})
        self.assertEqual(res["status"], "success")
        data = res["result"]
        self.assertEqual(data["level"], SafetyLevel.HIGH_RISK.value)
        self.assertIn("delete allow 443/tcp", data.get("suggested_rollback", ""))

    def test_react_agent_observation_gathering(self):
        custom_logs = [
            LogRecord(
                timestamp="now",
                source="journald",
                priority="3",
                message="[emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)",
                unit="nginx.service"
            )
        ]
        rep = self.agent.diagnose("Why is NGINX failing to bind to port 80?", custom_logs=custom_logs)
        self.assertEqual(rep.target_subsystem, "nginx")
        self.assertIn("bound", rep.explanation.root_cause.lower())
        self.assertIsNotNone(rep.causality_dag)
        self.assertGreater(len(rep.explanation.proposed_commands), 0)

    def test_react_agent_with_mock_tool_calling_llm(self):
        mock_llm = MagicMock()
        mock_llm.generate_diagnosis.return_value = {
            "symptom": "Upstream Node.js process crashed",
            "root_cause": "Node daemon killed by OOM killer, causing port 3000 socket closure",
            "rationale": "Kernel dmesg confirms OOM kill of node process",
            "proposed_commands": [
                ["sudo journalctl -u node-app -n 50", "READ_ONLY", 0.05, "Inspect Node.js crash trace"],
                ["sudo systemctl restart node-app", "MODIFYING", 0.35, "Restart Node.js service"]
            ],
            "confidence": 0.95
        }

        agent = ReActAgent(llm_provider=mock_llm)
        rep = agent.diagnose("Nginx returning 502 Bad Gateway to upstream 3000", custom_logs=[])
        self.assertIn("Upstream Node.js process crashed", rep.explanation.symptom)
        self.assertEqual(len(rep.explanation.proposed_commands), 2)
        self.assertEqual(rep.explanation.proposed_commands[1].safety_level, SafetyLevel.MODIFYING)


if __name__ == "__main__":
    unittest.main()
