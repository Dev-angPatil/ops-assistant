"""Comprehensive unit tests for the Dynamic ReAct Tool-Calling Loop & Multi-Turn Session Memory."""

import unittest
from unittest.mock import MagicMock, patch

from ops_assistant.agent.core import ReActAgent
from ops_assistant.agent.session import ConversationSession, ConversationTurn
from ops_assistant.agent.tools_registry import AgentToolsRegistry
from ops_assistant.nlp.intent_router import IntentRouter, IntentType
from ops_assistant.models import SafetyLevel


class TestReActToolCallingLoop(unittest.TestCase):
    def setUp(self):
        self.session = ConversationSession()
        self.mock_llm = MagicMock()
        self.mock_llm.is_available.return_value = (True, "Ready")

    def test_dynamic_plan_observations_execution(self):
        """Test that the ReAct loop calls plan_observations and dynamically runs planned tools."""
        self.mock_llm.plan_observations.return_value = [
            {"tool": "inspect_listening_ports", "arguments": {"port": 80}},
            {"tool": "inspect_service", "arguments": {"service_name": "nginx"}}
        ]
        self.mock_llm.generate_diagnosis.return_value = None
        self.mock_llm.synthesize_diagnosis.return_value = {
            "symptom": "Port collision on 80 and nginx inactive",
            "root_cause": "Apache holds port 80 socket, preventing nginx from binding",
            "rationale": "Observation confirmed apache2 PID bound to 0.0.0.0:80",
            "proposed_commands": [
                ["sudo systemctl stop apache2", "MODIFYING", 0.35, "Stop conflicting Apache web server"],
                ["sudo systemctl start nginx", "MODIFYING", 0.35, "Start Nginx web server"]
            ],
            "confidence": 0.98
        }

        agent = ReActAgent(llm_provider=self.mock_llm, session=self.session)
        rep = agent.diagnose("Why is NGINX failing to bind to port 80?")

        # Verify plan_observations was called with tool schemas
        self.mock_llm.plan_observations.assert_called_once()
        call_args = self.mock_llm.plan_observations.call_args[0]
        self.assertIn("Why is NGINX failing", call_args[0])
        self.assertIsInstance(call_args[2], list)  # tool schemas

        # Verify synthesize_diagnosis was called with the collected observations
        self.mock_llm.synthesize_diagnosis.assert_called_once()
        syn_args = self.mock_llm.synthesize_diagnosis.call_args[0]
        observations = syn_args[2]
        observed_tools = {o["tool"] for o in observations}
        self.assertIn("inspect_listening_ports", observed_tools)
        self.assertIn("inspect_service", observed_tools)

        # Verify report outputs
        self.assertEqual(rep.target_subsystem, "nginx")
        self.assertIn("Port collision", rep.explanation.symptom)
        self.assertEqual(len(rep.explanation.proposed_commands), 2)


class TestMultiTurnConversationSession(unittest.TestCase):
    def setUp(self):
        self.session = ConversationSession()

    def test_session_records_turns(self):
        self.session.add_turn(
            query="Why is postgresql down?",
            response_summary="Postgres crashed due to OOM kill",
            intent="diagnose",
            subsystem="postgresql",
            commands=["sudo systemctl restart postgresql"],
            symptom="OOM kill",
            root_cause="Out of memory"
        )
        self.assertEqual(len(self.session.turns), 1)
        self.assertEqual(self.session.active_subsystem, "postgresql")
        self.assertIn("Turn 1:", self.session.get_context_for_llm())

    def test_pronoun_resolution_for_service_logs(self):
        self.session.add_turn(
            query="why is nginx crashing?",
            response_summary="Nginx crashed",
            subsystem="nginx"
        )
        resolved = self.session.resolve_pronouns("what about its logs?")
        self.assertEqual(resolved, "what about nginx logs?")

    def test_pronoun_resolution_for_status(self):
        self.session.add_turn(
            query="check mysql",
            response_summary="MySQL status check",
            subsystem="mysql"
        )
        resolved = self.session.resolve_pronouns("why is it failing?")
        self.assertEqual(resolved, "why is mysql failing?")

    def test_pronoun_resolution_for_fix_it(self):
        self.session.add_turn(
            query="diagnose redis",
            response_summary="Redis stopped",
            subsystem="redis",
            commands=["sudo systemctl restart redis"]
        )
        resolved = self.session.resolve_pronouns("fix it")
        self.assertEqual(resolved, "Execute remediation commands: sudo systemctl restart redis")


class TestIntentRouterLLMFallback(unittest.TestCase):
    def test_llm_fallback_for_novel_phrasing(self):
        mock_llm = MagicMock()
        mock_llm.generate_raw.return_value = '{"intent": "storage_clean", "args": {"dry_run": true}}'

        router = IntentRouter(llm_provider=mock_llm)
        intent = router.classify("sweep away any junk files consuming my drive")
        self.assertEqual(intent.type, IntentType.STORAGE_CLEAN)
        self.assertEqual(intent.args.get("dry_run"), True)


if __name__ == "__main__":
    unittest.main()
