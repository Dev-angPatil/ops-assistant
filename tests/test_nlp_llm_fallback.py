import unittest
from ops_assistant.nlp.intent_router import IntentRouter, IntentType, _sanitize_arg, _sanitize_token
from ops_assistant.agent import LLMProvider


class MockLLMProvider(LLMProvider):
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_history = []

    def generate_raw(self, prompt: str, max_tokens: int = 512, temperature: float = 0.2, repeat_penalty: float = 1.15) -> str:
        self.call_history.append(prompt)
        return self.responses.get("raw", '{"intent": "storage_analyse", "args": {}}')

    def generate_diagnosis(self, query: str, context: dict) -> dict:
        self.call_history.append((query, context))
        if context.get("prompt"):
            raw = self.generate_raw(context["prompt"])
            import json
            return json.loads(raw)
        return self.responses.get("diagnosis", {"symptom": "mock", "root_cause": "mock"})


class TestNLPAndLLMFallback(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_argument_sanitization(self):
        # Null bytes and control characters stripped
        dirty = "nginx\x00\x01\x1f; rm -rf /"
        cleaned = _sanitize_token(dirty)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn(";", cleaned)
        self.assertNotIn("/", cleaned)

    def test_nlp_intent_classification(self):
        cases = [
            ("what is eating my disk space", IntentType.STORAGE_FIND_LARGE),
            ("show disk usage", IntentType.STORAGE_ANALYSE),
            ("clean up old logs", IntentType.STORAGE_CLEAN),
            ("organise ~/Downloads", IntentType.STORAGE_ORGANISE),
            ("list running processes", IntentType.PROCESS_LIST),
            ("kill process 1234", IntentType.PROCESS_KILL),
            ("status of nginx", IntentType.SERVICE_STATUS),
            ("restart docker", IntentType.SERVICE_RESTART),
            ("who is logged in", IntentType.USER_WHO),
            ("show crontab", IntentType.CRON_LIST),
            ("check for ssh brute force attacks", IntentType.SECURITY_BRUTEFORCE),
            ("audit suid binaries", IntentType.SECURITY_SUID),
            ("backup /etc to /tmp", IntentType.BACKUP_CREATE),
            ("profile hardware capabilities", IntentType.HARDWARE_PROFILE),
            ("which ai model should i download", IntentType.HARDWARE_RECOMMEND_MODEL),
        ]
        for text, expected in cases:
            intent = self.router.classify(text)
            self.assertEqual(intent.type, expected, f"Failed on '{text}': got {intent.type}, expected {expected}")

    def test_llm_fallback_classification(self):
        mock_p = MockLLMProvider({"raw": '{"intent": "security_audit", "args": {}}'})
        router_with_llm = IntentRouter(llm_provider=mock_p)
        intent = router_with_llm.classify("completely unclassified obscure inquiry that fails regex matching")
        self.assertEqual(intent.type, IntentType.SECURITY_AUDIT)

    def test_agent_automatic_fallback_to_llm_generation(self):
        from ops_assistant.agent import OpsAssistantAgent
        from ops_assistant.agent.providers import _parse_llm_json

        # Test _parse_llm_json robustness
        raw_fence = "```json\n{\n  \"command\": \"find / -name '*.log'\",\n  \"summary\": \"Find logs\"\n}\n```"
        parsed = _parse_llm_json(raw_fence)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["command"], "find / -name '*.log'")

        raw_plain_cmd = "tar -czf backup.tar.gz /var/www"
        parsed_plain = _parse_llm_json(raw_plain_cmd)
        self.assertIsNotNone(parsed_plain)
        self.assertEqual(parsed_plain["command"], "tar -czf backup.tar.gz /var/www")

        # Mock LLM provider that generates a custom command
        class CommandMockProvider(LLMProvider):
            def is_available(self):
                return True, "Ready"
            def generate_command(self, query, cwd=None):
                return {
                    "command": "find /var/log -type f -name '*.gz' -delete",
                    "summary": "Delete old gzip compressed logs in /var/log",
                    "safety_level": "MODIFYING",
                    "risk_score": 0.45,
                    "rollback_command": None
                }

        agent = OpsAssistantAgent(llm_provider=CommandMockProvider())
        act = agent.execute_agent_action(
            "purge every gzip log file residing under the var log directory",
            execute=False
        )
        self.assertEqual(act["intent"], "llm_generated_command")
        self.assertIn("find /var/log", act["command"])
        self.assertEqual(act["summary"], "Delete old gzip compressed logs in /var/log")
        self.assertTrue(bool(act.get("explanation_paragraph")))


if __name__ == "__main__":
    unittest.main()
