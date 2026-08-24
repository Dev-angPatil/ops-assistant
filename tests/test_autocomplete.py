"""
Unit and Integration Tests for Natural Language Autocomplete Subsystem.
Tests both the core engine, context providers, history matching, CLI completer, and GUI endpoints.
"""

import os
import time
import json
import tempfile
import urllib.request
import threading
import unittest

from ops_assistant.nlp.autocomplete import AutocompleteEngine, Suggestion, get_autocomplete_engine
from ops_assistant.db.history_db import HistoryDatabase
from ops_assistant.gui.server import start_gui_server
from ops_assistant.agent import OpsAssistantAgent
from ops_assistant.cli import CLIAutocompleteCompleter, HAS_PROMPT_TOOLKIT


class TestAutocompleteSubsystem(unittest.TestCase):

    def test_autocomplete_prefix_matching(self):
        """Tests standard prefix matching across common Linux tasks."""
        engine = AutocompleteEngine()

        # 1. 'inst' -> Install tasks
        res_inst = engine.suggest("inst", max_results=8)
        self.assertTrue(len(res_inst) > 0)
        texts_inst = [s.text for s in res_inst]
        self.assertTrue(any("Install" in t for t in texts_inst))
        self.assertTrue(any("dependencies" in t.lower() or "python" in t.lower() or "docker" in t.lower() or "git" in t.lower() for t in texts_inst))

        # 2. 'check' -> Check CPU, RAM, disk, battery
        res_check = engine.suggest("check", max_results=8)
        self.assertGreaterEqual(len(res_check), 4)
        texts_check = [s.text for s in res_check]
        self.assertIn("Check CPU usage", texts_check)
        self.assertIn("Check RAM usage", texts_check)
        self.assertIn("Check disk usage", texts_check)
        self.assertIn("Check battery health", texts_check)

        # 3. 'organ' -> Organize Downloads, project, desktop
        res_organ = engine.suggest("organ", max_results=8)
        self.assertGreaterEqual(len(res_organ), 3)
        texts_organ = [s.text for s in res_organ]
        self.assertTrue(any("Downloads" in t for t in texts_organ))
        self.assertTrue(any("project" in t.lower() for t in texts_organ))
        self.assertTrue(any("desktop" in t.lower() for t in texts_organ))

    def test_smart_intent_semantic_matching(self):
        """Tests semantic and intent-based understanding rather than raw keyword matches."""
        engine = AutocompleteEngine()

        # 1. "my laptop is slow" -> CPU, RAM, high resource processes
        slow_suggs = engine.suggest("my laptop is slow", max_results=6)
        self.assertGreaterEqual(len(slow_suggs), 3)
        slow_texts = [s.text for s in slow_suggs]
        self.assertIn("Check CPU usage", slow_texts)
        self.assertIn("Check RAM usage", slow_texts)
        self.assertIn("Find high resource processes", slow_texts)
        self.assertEqual(slow_suggs[0].category, "smart_intent")

        # 2. "python project" -> venv, requirements, run project
        py_suggs = engine.suggest("python project", max_results=6)
        self.assertGreaterEqual(len(py_suggs), 2)
        py_texts = [s.text for s in py_suggs]
        self.assertTrue(any("virtual environment" in t.lower() or "venv" in t.lower() for t in py_texts))
        self.assertTrue(any("requirements" in t.lower() or "install" in t.lower() for t in py_texts))

        # 3. "free space" -> Check disk usage, Find large files, Clean Trash
        disk_suggs = engine.suggest("free space", max_results=6)
        self.assertGreaterEqual(len(disk_suggs), 3)
        disk_texts = [s.text for s in disk_suggs]
        self.assertIn("Check disk usage", disk_texts)
        self.assertIn("Find large files", disk_texts)
        self.assertIn("Clean Trash", disk_texts)

        # 4. "clean" -> Clean up old logs, Clean Trash, Purge cache
        clean_suggs = engine.suggest("clean", max_results=6)
        self.assertGreaterEqual(len(clean_suggs), 3)
        clean_texts = [s.text for s in clean_suggs]
        self.assertTrue(any("Clean up old logs" in t or "Clean Trash" in t for t in clean_texts))

    def test_project_context_discovery(self):
        """Tests dynamic project context detection based on workspace files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"name": "test-app"}')
            with open(os.path.join(tmpdir, "Dockerfile"), "w") as f:
                f.write("FROM node:18")

            engine = AutocompleteEngine()
            suggs = engine.suggest("", cwd=tmpdir, max_results=10)
            texts = [s.text for s in suggs]
            categories = [s.category for s in suggs]

            self.assertIn("Install Node.js dependencies", texts)
            self.assertIn("Build Docker image", texts)
            self.assertIn("project", categories)

    def test_history_suggestions_integration(self):
        """Tests reading and prioritizing past executed queries from SQLite history."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_history.db")
            temp_history_db = HistoryDatabase(db_path=db_path)

            temp_history_db.log_command(
                query="restart postgresql database",
                command="sudo systemctl restart postgresql",
                intent="service_restart"
            )
            temp_history_db.log_command(
                query="restart nginx web server",
                command="sudo systemctl restart nginx",
                intent="service_restart"
            )

            engine = AutocompleteEngine(history_db=temp_history_db)
            suggs = engine.suggest("restart post", max_results=5)
            self.assertTrue(len(suggs) > 0)
            self.assertTrue(any("restart postgresql" in s.text.lower() for s in suggs))
            hist_items = [s for s in suggs if s.category == "history"]
            self.assertGreaterEqual(len(hist_items), 1)
            self.assertEqual(hist_items[0].command_preview, "sudo systemctl restart postgresql")

    def test_highlight_ranges_calculation(self):
        """Tests accuracy of start and end character highlighting ranges."""
        engine = AutocompleteEngine()

        # Exact prefix highlight
        ranges = engine.calculate_highlight_ranges("Install Docker", "inst")
        self.assertEqual(ranges, [(0, 4)])

        # Multi-token highlight
        ranges2 = engine.calculate_highlight_ranges("Check CPU usage", "check usage")
        self.assertIn((0, 5), ranges2)
        self.assertIn((10, 15), ranges2)

    def test_autocomplete_performance_under_10ms(self):
        """Validates that suggestion generation is exceptionally fast (< 10ms, far below 100ms target)."""
        engine = AutocompleteEngine()
        test_queries = ["inst", "check", "organ", "free space", "my laptop is slow", "git", "clean", "docker"]

        # Warmup
        for q in test_queries:
            engine.suggest(q)

        # Benchmark
        start = time.perf_counter()
        iterations = 50
        for _ in range(iterations):
            for q in test_queries:
                suggs = engine.suggest(q)
                self.assertTrue(len(suggs) > 0)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / (iterations * len(test_queries))) * 1000
        self.assertLess(avg_ms, 10.0, f"Average autocomplete latency {avg_ms:.2f}ms exceeds 10ms threshold")

    def test_gui_autocomplete_endpoints(self):
        """Tests GET and POST /api/autocomplete endpoints on GUI HTTP server."""
        agent = OpsAssistantAgent()
        server, url = start_gui_server(host="127.0.0.1", port=9944, open_browser=False, agent=agent)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.2)

        try:
            # 1. GET /api/autocomplete?q=inst
            req_get = urllib.request.Request(f"{url}/api/autocomplete?q=inst&limit=5", headers={"Connection": "close"})
            with urllib.request.urlopen(req_get, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["success"])
                self.assertEqual(data["query"], "inst")
                self.assertTrue(len(data["suggestions"]) > 0)
                self.assertTrue(any("Install" in s["text"] for s in data["suggestions"]))

            # 2. POST /api/autocomplete
            payload = json.dumps({"query": "check", "limit": 6}).encode("utf-8")
            req_post = urllib.request.Request(
                f"{url}/api/autocomplete",
                data=payload,
                headers={"Content-Type": "application/json", "Connection": "close"}
            )
            with urllib.request.urlopen(req_post, timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(data["success"])
                self.assertEqual(data["query"], "check")
                self.assertGreaterEqual(len(data["suggestions"]), 4)
                texts = [s["text"] for s in data["suggestions"]]
                self.assertIn("Check CPU usage", texts)

        finally:
            server.shutdown()
            server.server_close()

    def test_cli_autocomplete_completer(self):
        """Tests CLI prompt_toolkit completer yields valid suggestions with metadata."""
        engine = AutocompleteEngine()
        completer = CLIAutocompleteCompleter(engine=engine)

        class DummyDoc:
            def __init__(self, text):
                self.text = text
                self.text_before_cursor = text

        doc = DummyDoc("organ")
        completions = list(completer.get_completions(doc, None))
        self.assertTrue(len(completions) > 0)
        display_texts = [c.display_text if hasattr(c, "display_text") else str(c.display) for c in completions]
        self.assertTrue(any("Downloads" in t for t in display_texts))

    def test_open_browser_and_action_intents(self):
        """Tests that typing 'open browser' or 'browser' suggests browser launch tasks."""
        engine = AutocompleteEngine()

        # 1. 'open browser'
        suggs_browser = engine.suggest("open browser", max_results=6)
        self.assertTrue(len(suggs_browser) > 0)
        texts = [s.text for s in suggs_browser]
        self.assertIn("Open web browser", texts)
        self.assertFalse(any("What ports are open" == t for t in texts))

        # 2. 'open terminal'
        suggs_term = engine.suggest("open terminal", max_results=6)
        self.assertTrue(any("Open terminal" in s.text for s in suggs_term))

        # 3. 'ports'
        suggs_ports = engine.suggest("ports", max_results=6)
        self.assertTrue(any("What ports are open" in s.text for s in suggs_ports))

    def test_multi_token_strict_filtering(self):
        """Tests that queries with multiple words strictly require all meaningful keywords."""
        engine = AutocompleteEngine()

        # 'open browser' should strictly match browser items, not port items that happen to contain 'open'
        suggs = engine.suggest("open browser", max_results=10)
        for s in suggs:
            lower_text = s.text.lower()
            lower_desc = s.description.lower()
            self.assertTrue(any(k in lower_text or k in lower_desc for k in ["browser", "chrome", "firefox", "brave", "web", "internet"]))


if __name__ == "__main__":
    unittest.main()
