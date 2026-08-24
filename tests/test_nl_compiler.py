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
        self.assertTrue(any(w in exp.lower() for w in ("successfully", "created")))
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

    def test_open_folders_with_typos(self):
        for q in ["open downlaods", "open downlaod", "open downlod", "open my downlaods folder"]:
            res = NaturalLanguageCompiler.compile(q)
            self.assertIsNotNone(res, f"Failed to compile {q}")
            self.assertEqual(res["intent"], "desktop_open_folder")
            self.assertIn("Downloads", res["command"])
            self.assertIn("xdg-open", res["command"])

        for q in ["open documnts", "open documnt", "open docs"]:
            res = NaturalLanguageCompiler.compile(q)
            self.assertIsNotNone(res, f"Failed to compile {q}")
            self.assertEqual(res["intent"], "desktop_open_folder")
            self.assertIn("Documents", res["command"])

    def test_open_custom_folder(self):
        query = "open folder divya"
        act = self.agent.execute_agent_action(query, execute=False)
        self.assertEqual(act["intent"], "desktop_open_folder")
        self.assertIn("xdg-open", act["command"])

    def test_file_permissions(self):
        q1 = "make script.sh executable"
        res1 = NaturalLanguageCompiler.compile(q1)
        self.assertIsNotNone(res1)
        self.assertEqual(res1["command"], "chmod +x 'script.sh'")
        self.assertEqual(res1["intent"], "perm_change")

        q2 = "change permission of file.txt to 755"
        res2 = NaturalLanguageCompiler.compile(q2)
        self.assertIsNotNone(res2)
        self.assertEqual(res2["command"], "chmod 755 'file.txt'")

    def test_compression_and_extraction(self):
        q1 = "compress folder Project to project.tar.gz"
        res1 = NaturalLanguageCompiler.compile(q1)
        self.assertIsNotNone(res1)
        self.assertIn("tar -czf 'project.tar.gz' 'Project'", res1["command"])
        self.assertEqual(res1["intent"], "archive_create")

        q2 = "extract archive project.tar.gz to /tmp"
        res2 = NaturalLanguageCompiler.compile(q2)
        self.assertIsNotNone(res2)
        self.assertIn("tar -xzf 'project.tar.gz' -C '/tmp'", res2["command"])
        self.assertEqual(res2["intent"], "archive_extract")

    def test_file_search_operations(self):
        q1 = "find all pdf files in Downloads"
        res1 = NaturalLanguageCompiler.compile(q1)
        self.assertIsNotNone(res1)
        self.assertIn("find", res1["command"])
        self.assertIn("*.pdf", res1["command"])

        q2 = "find files larger than 100MB in ~/Downloads"
        res2 = NaturalLanguageCompiler.compile(q2)
        self.assertIsNotNone(res2)
        self.assertIn("find", res2["command"])
        self.assertIn("-size +100M", res2["command"])

        q3 = "search for 'TODO' in src"
        res3 = NaturalLanguageCompiler.compile(q3)
        self.assertIsNotNone(res3)
        self.assertIn("grep", res3["command"])
        self.assertIn("TODO", res3["command"])

    def test_git_operations(self):
        res1 = NaturalLanguageCompiler.compile("git status")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["command"], "git status")

        res2 = NaturalLanguageCompiler.compile("show git branch")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["command"], "git branch -a")

        res3 = NaturalLanguageCompiler.compile("show git log")
        self.assertIsNotNone(res3)
        self.assertIn("git log", res3["command"])

    def test_hardware_and_network_extensions(self):
        res1 = NaturalLanguageCompiler.compile("check battery")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["intent"], "system_battery")

        res2 = NaturalLanguageCompiler.compile("show gpu info")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["intent"], "hardware_profile")

        res3 = NaturalLanguageCompiler.compile("what is my public ip")
        self.assertIsNotNone(res3)
        self.assertIn("ifconfig.me", res3["command"])

    def test_popular_sites_extension(self):
        res1 = NaturalLanguageCompiler.compile("open claude")
        self.assertIsNotNone(res1)
        self.assertIn("claude.ai", res1["command"])

        res2 = NaturalLanguageCompiler.compile("open kaggle")
        self.assertIsNotNone(res2)
        self.assertIn("kaggle.com", res2["command"])


if __name__ == "__main__":
    unittest.main()
