"""Unit and Integration Tests for ExecutionOutcomeExplainer."""

import io
import sys
import unittest
from ops_assistant.explainer.xai import ExecutionOutcomeExplainer, ErrorExplainer, CommandExplainer
from ops_assistant.agent import OpsAssistantAgent
from ops_assistant.cli import render_execution_outcome


class MockLLMProvider:
    def __init__(self, response="AI elaborated explanation"):
        self.response = response

    def _call_gemini_api(self, prompt, response_json=False):
        return self.response

    def generate(self, prompt):
        return self.response


class TestExecutionExplainer(unittest.TestCase):

    def test_outcome_explainer_mkdir_success(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="mkdir -p /tmp/ops_test_dir",
            returncode=0,
            stdout="",
            stderr="",
            query="create test folder"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue("mkdir" in outcome["natural_explanation"].lower() or "directory" in outcome["natural_explanation"].lower())
        self.assertTrue(len(outcome["changes_made"]) > 0)
        self.assertTrue(any("/tmp/ops_test_dir" in c for c in outcome["changes_made"]))
        self.assertIsNone(outcome["failure_analysis"])

    def test_outcome_explainer_service_start_success(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="sudo systemctl start nginx",
            returncode=0,
            stdout="",
            stderr="",
            query="start nginx web server"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("nginx" in c and "start" in c.lower() for c in outcome["changes_made"]))
        self.assertIsNone(outcome["failure_analysis"])

    def test_outcome_explainer_service_stop_success(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="sudo systemctl stop apache2",
            returncode=0,
            stdout="",
            stderr="",
            query="stop apache"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("apache2" in c and "stop" in c.lower() for c in outcome["changes_made"]))

    def test_outcome_explainer_package_install_success(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="sudo apt-get install -y htop curl",
            returncode=0,
            stdout="Setting up htop ...\nSetting up curl ...",
            stderr="",
            query="install htop and curl"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("htop" in c for c in outcome["changes_made"]))
        self.assertTrue(any("curl" in c for c in outcome["changes_made"]))

    def test_outcome_explainer_file_delete_success(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="rm -rf /tmp/cached_data",
            returncode=0,
            stdout="",
            stderr="",
            query="delete cached data"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("Deleted" in c and "/tmp/cached_data" in c for c in outcome["changes_made"]))

    def test_outcome_explainer_process_kill(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="kill -9 98765",
            returncode=0,
            stdout="",
            stderr="",
            query="kill process 98765"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("98765" in c for c in outcome["changes_made"]))

    def test_outcome_explainer_permissions(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="chmod +x /usr/local/bin/my_script.sh",
            returncode=0,
            stdout="",
            stderr="",
            query="make script executable"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("/usr/local/bin/my_script.sh" in c for c in outcome["changes_made"]))

    def test_outcome_explainer_firewall_allow(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="sudo ufw allow 8080/tcp",
            returncode=0,
            stdout="Rules updated",
            stderr="",
            query="open port 8080"
        )
        self.assertTrue(outcome["is_success"])
        self.assertTrue(any("8080" in c for c in outcome["changes_made"]))

    def test_outcome_explainer_failure_command_not_found(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="foobar_nonexistent_cli --run",
            returncode=127,
            stdout="",
            stderr="bash: foobar_nonexistent_cli: command not found",
            query="run nonexistent tool"
        )
        self.assertFalse(outcome["is_success"])
        self.assertIsNotNone(outcome["failure_analysis"])
        self.assertEqual(outcome["failure_analysis"]["error_class"], "COMMAND_NOT_FOUND")
        self.assertTrue("not installed" in outcome["failure_analysis"]["diagnosis"].lower() or "not found" in outcome["failure_analysis"]["diagnosis"].lower())
        self.assertNotEqual(outcome["failure_analysis"]["recommendation"], "")

    def test_outcome_explainer_failure_permission_denied(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="systemctl restart sshd",
            returncode=1,
            stdout="",
            stderr="Failed to restart sshd.service: Interactive authentication required.",
            query="restart ssh"
        )
        self.assertFalse(outcome["is_success"])
        self.assertIsNotNone(outcome["failure_analysis"])
        self.assertIn(outcome["failure_analysis"]["error_class"], ("PERMISSION_DENIED", "INSUFFICIENT_PRIVILEGES"))
        self.assertTrue("sudo" in outcome["failure_analysis"]["recommendation"].lower() or "root" in outcome["failure_analysis"]["recommendation"].lower())

    def test_outcome_explainer_failure_file_not_found(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="cat /var/log/nonexistent.log",
            returncode=1,
            stdout="",
            stderr="cat: /var/log/nonexistent.log: No such file or directory",
            query="view log"
        )
        self.assertFalse(outcome["is_success"])
        self.assertIsNotNone(outcome["failure_analysis"])
        self.assertEqual(outcome["failure_analysis"]["error_class"], "FILE_NOT_FOUND")

    def test_outcome_explainer_failure_port_conflict(self):
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="nginx -g 'daemon off;'",
            returncode=1,
            stdout="",
            stderr="nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)",
            query="start nginx"
        )
        self.assertFalse(outcome["is_success"])
        self.assertIsNotNone(outcome["failure_analysis"])
        self.assertEqual(outcome["failure_analysis"]["error_class"], "PORT_CONFLICT")
        self.assertIn("80", outcome["failure_analysis"]["diagnosis"])

    def test_outcome_explainer_with_llm_provider(self):
        mock_llm = MockLLMProvider("AI model generated detailed explanation of changes and impact.")
        outcome = ExecutionOutcomeExplainer.explain_outcome(
            command="mkdir -p /tmp/ai_explained",
            returncode=0,
            stdout="",
            stderr="",
            query="create directory",
            llm_provider=mock_llm
        )
        self.assertTrue(outcome["is_success"])
        self.assertEqual(outcome["ai_elaboration"], "AI model generated detailed explanation of changes and impact.")

    def test_agent_explain_execution_outcome(self):
        agent = OpsAssistantAgent()
        res = agent.explain_execution_outcome(
            command_str="touch /tmp/test_file.txt",
            returncode=0,
            stdout="",
            stderr="",
            query="create test file"
        )
        self.assertTrue(res["is_success"])
        self.assertTrue(len(res["changes_made"]) > 0)
        self.assertTrue(any("/tmp/test_file.txt" in c for c in res["changes_made"]))

    def test_agent_execute_agent_action_enriches_outcome(self):
        agent = OpsAssistantAgent()
        plan = agent.execute_agent_action("create folder /tmp/ops_my_new_folder", execute=False)
        self.assertIn("explanation_paragraph", plan)
        self.assertIn("ai_explanation", plan)
        self.assertIn("changes_made", plan)
        self.assertIn("is_success", plan)

    def test_cli_render_execution_outcome_smoke(self):
        outcome = {
            "is_success": True,
            "natural_explanation": "Created folder /tmp/test successfully.",
            "changes_made": ["Created directory: /tmp/test"],
            "failure_analysis": None
        }
        captured = io.StringIO()
        orig = sys.stdout
        try:
            sys.stdout = captured
            render_execution_outcome(outcome)
        finally:
            sys.stdout = orig
        out = captured.getvalue()
        self.assertTrue("Created" in out or len(out) > 0)

    def test_cli_render_execution_outcome_failure_smoke(self):
        outcome = {
            "is_success": False,
            "returncode": 127,
            "natural_explanation": "Failed to run command.",
            "changes_made": [],
            "failure_analysis": {
                "error_class": "COMMAND_NOT_FOUND",
                "diagnosis": "Binary missing from PATH.",
                "recommendation": "Install using package manager."
            }
        }
        captured = io.StringIO()
        orig = sys.stdout
        try:
            sys.stdout = captured
            render_execution_outcome(outcome)
        finally:
            sys.stdout = orig
        out = captured.getvalue()
        self.assertTrue("COMMAND_NOT_FOUND" in out or len(out) > 0)


if __name__ == "__main__":
    unittest.main()
