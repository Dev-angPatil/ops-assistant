import unittest
from ops_assistant.nlp.nl_compiler import NaturalLanguageCompiler, generate_natural_explanation
from ops_assistant.nlp.intent_router import IntentRouter, IntentType
from ops_assistant.agent import OpsAssistantAgent

class TestNLCompiler(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()
        self.agent = OpsAssistantAgent()

    def test_nested_folder_creation(self):
        query = "inside Divya create one folder name as DBMS"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertIn("mkdir -p 'Divya/DBMS'", res["command"])

        # Agent interpret & execute_agent_action
        act = self.agent.execute_agent_action(query, execute=False)
        self.assertIn("mkdir -p", act["command"])
        self.assertIn("Divya/DBMS", act["command"])
        self.assertTrue(bool(act.get("explanation_paragraph")))

    def test_open_youtube(self):
        query = "open YouTube"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertIn("xdg-open 'https://youtube.com'", res["command"])

        act = self.agent.execute_agent_action(query, execute=False)
        self.assertIn("youtube.com", act["command"])

    def test_open_leetcode(self):
        query = "open lead code platform"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertIn("leetcode.com", res["command"])

    def test_open_dsa_folder(self):
        query = "open my DSA folder"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertIn("xdg-open", res["command"])
        self.assertIn("DSA", res["command"])

    def test_open_brave(self):
        query = "open brave Browser"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertTrue(any(b in res["command"] for b in ("brave", "xdg-open")))

    def test_cpu_uses(self):
        query = "check my CPU uses"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertIn("top", res["command"])

    def test_natural_explanation_generation(self):
        exp = generate_natural_explanation("create folder test", "mkdir -p test", 0, "", "")
        self.assertIn("Successfully created", exp)
        self.assertIn("test", exp)

    def test_rename_latest_screenshot(self):
        query = 'rename the latest screen shot to "imp"'
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertEqual(res["intent"], "file_rename")
        self.assertIn("imp", res["command"])
        self.assertIn("find", res["command"])

    def test_rename_file(self):
        query = "rename file old_notes.txt to new_notes.txt"
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertEqual(res["intent"], "file_rename")
        self.assertEqual(res["command"], "mv 'old_notes.txt' 'new_notes.txt'")

    def test_rename_downloads_folder(self):
        query = 'rename the downloads to "downloaded"'
        res = NaturalLanguageCompiler.compile(query)
        self.assertIsNotNone(res)
        self.assertEqual(res["intent"], "file_rename")
        self.assertEqual(res["command"], "mv 'downloads' 'downloaded'")

        query2 = "rename the downloads folder to downloaded"
        res2 = NaturalLanguageCompiler.compile(query2)
        self.assertIsNotNone(res2)
        self.assertEqual(res2["command"], "mv 'downloads' 'downloaded'")


if __name__ == "__main__":
    unittest.main()
