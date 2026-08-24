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
import pytest

from ops_assistant.nlp.autocomplete import AutocompleteEngine, Suggestion, get_autocomplete_engine
from ops_assistant.db.history_db import HistoryDatabase
from ops_assistant.gui.server import start_gui_server
from ops_assistant.agent import OpsAssistantAgent
from ops_assistant.cli import CLIAutocompleteCompleter, HAS_PROMPT_TOOLKIT


@pytest.fixture
def temp_history_db():
    """Creates a temporary isolated SQLite history database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_history.db")
        db = HistoryDatabase(db_path=db_path)
        yield db


def test_autocomplete_prefix_matching():
    """Tests standard prefix matching across common Linux tasks."""
    engine = AutocompleteEngine()

    # 1. 'inst' -> Install tasks
    res_inst = engine.suggest("inst", max_results=8)
    assert len(res_inst) > 0
    texts_inst = [s.text for s in res_inst]
    assert any("Install" in t for t in texts_inst)
    assert any("dependencies" in t.lower() or "python" in t.lower() or "docker" in t.lower() or "git" in t.lower() for t in texts_inst)

    # 2. 'check' -> Check CPU, RAM, disk, battery
    res_check = engine.suggest("check", max_results=8)
    assert len(res_check) >= 4
    texts_check = [s.text for s in res_check]
    assert "Check CPU usage" in texts_check
    assert "Check RAM usage" in texts_check
    assert "Check disk usage" in texts_check
    assert "Check battery health" in texts_check

    # 3. 'organ' -> Organize Downloads, project, desktop
    res_organ = engine.suggest("organ", max_results=8)
    assert len(res_organ) >= 3
    texts_organ = [s.text for s in res_organ]
    assert any("Downloads" in t for t in texts_organ)
    assert any("project" in t.lower() for t in texts_organ)
    assert any("desktop" in t.lower() for t in texts_organ)


def test_smart_intent_semantic_matching():
    """Tests semantic and intent-based understanding rather than raw keyword matches."""
    engine = AutocompleteEngine()

    # 1. "my laptop is slow" -> CPU, RAM, high resource processes
    slow_suggs = engine.suggest("my laptop is slow", max_results=6)
    assert len(slow_suggs) >= 3
    slow_texts = [s.text for s in slow_suggs]
    assert "Check CPU usage" in slow_texts
    assert "Check RAM usage" in slow_texts
    assert "Find high resource processes" in slow_texts
    assert slow_suggs[0].category == "smart_intent"

    # 2. "python project" -> venv, requirements, run project
    py_suggs = engine.suggest("python project", max_results=6)
    assert len(py_suggs) >= 2
    py_texts = [s.text for s in py_suggs]
    assert any("virtual environment" in t.lower() or "venv" in t.lower() for t in py_texts)
    assert any("requirements" in t.lower() or "install" in t.lower() for t in py_texts)

    # 3. "free space" -> Check disk usage, Find large files, Clean Trash
    disk_suggs = engine.suggest("free space", max_results=6)
    assert len(disk_suggs) >= 3
    disk_texts = [s.text for s in disk_suggs]
    assert "Check disk usage" in disk_texts
    assert "Find large files" in disk_texts
    assert "Clean Trash" in disk_texts

    # 4. "clean" -> Clean up old logs, Clean Trash, Purge cache
    clean_suggs = engine.suggest("clean", max_results=6)
    assert len(clean_suggs) >= 3
    clean_texts = [s.text for s in clean_suggs]
    assert any("Clean up old logs" in t or "Clean Trash" in t for t in clean_texts)


def test_project_context_discovery():
    """Tests dynamic project context detection based on workspace files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock Node + Docker workspace
        with open(os.path.join(tmpdir, "package.json"), "w") as f:
            f.write('{"name": "test-app"}')
        with open(os.path.join(tmpdir, "Dockerfile"), "w") as f:
            f.write("FROM node:18")

        engine = AutocompleteEngine()
        suggs = engine.suggest("", cwd=tmpdir, max_results=10)
        texts = [s.text for s in suggs]
        categories = [s.category for s in suggs]

        assert "Install Node.js dependencies" in texts
        assert "Build Docker image" in texts
        assert "project" in categories


def test_history_suggestions_integration(temp_history_db):
    """Tests reading and prioritizing past executed queries from SQLite history."""
    # Seed history database
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
    assert len(suggs) > 0
    assert any("restart postgresql" in s.text.lower() for s in suggs)
    hist_items = [s for s in suggs if s.category == "history"]
    assert len(hist_items) >= 1
    assert hist_items[0].command_preview == "sudo systemctl restart postgresql"


def test_highlight_ranges_calculation():
    """Tests accuracy of start and end character highlighting ranges."""
    engine = AutocompleteEngine()

    # Exact prefix highlight
    ranges = engine.calculate_highlight_ranges("Install Docker", "inst")
    assert ranges == [(0, 4)]

    # Multi-token highlight
    ranges2 = engine.calculate_highlight_ranges("Check CPU usage", "check usage")
    assert (0, 5) in ranges2
    assert (10, 15) in ranges2


def test_autocomplete_performance_under_10ms():
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
            assert len(suggs) > 0
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / (iterations * len(test_queries))) * 1000
    assert avg_ms < 10.0, f"Average autocomplete latency {avg_ms:.2f}ms exceeds 10ms threshold"


def test_gui_autocomplete_endpoints():
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
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["query"] == "inst"
            assert len(data["suggestions"]) > 0
            assert any("Install" in s["text"] for s in data["suggestions"])

        # 2. POST /api/autocomplete
        payload = json.dumps({"query": "check", "limit": 6}).encode("utf-8")
        req_post = urllib.request.Request(
            f"{url}/api/autocomplete",
            data=payload,
            headers={"Content-Type": "application/json", "Connection": "close"}
        )
        with urllib.request.urlopen(req_post, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["success"] is True
            assert data["query"] == "check"
            assert len(data["suggestions"]) >= 4
            texts = [s["text"] for s in data["suggestions"]]
            assert "Check CPU usage" in texts

    finally:
        server.shutdown()
        server.server_close()


def test_cli_autocomplete_completer():
    """Tests CLI prompt_toolkit completer yields valid suggestions with metadata."""
    engine = AutocompleteEngine()
    completer = CLIAutocompleteCompleter(engine=engine)

    class DummyDoc:
        def __init__(self, text):
            self.text = text
            self.text_before_cursor = text

    doc = DummyDoc("organ")
    completions = list(completer.get_completions(doc, None))
    assert len(completions) > 0
    display_texts = [c.display_text if hasattr(c, "display_text") else str(c.display) for c in completions]
    assert any("Downloads" in t for t in display_texts)


def test_open_browser_and_action_intents():
    """Tests that typing 'open browser' or 'browser' suggests browser launch tasks."""
    engine = AutocompleteEngine()

    # 1. 'open browser'
    suggs_browser = engine.suggest("open browser", max_results=6)
    assert len(suggs_browser) > 0
    texts = [s.text for s in suggs_browser]
    assert "Open web browser" in texts
    assert not any("What ports are open" == t for t in texts)  # Should NOT match ports query!

    # 2. 'open terminal'
    suggs_term = engine.suggest("open terminal", max_results=6)
    assert any("Open terminal" in s.text for s in suggs_term)

    # 3. 'ports'
    suggs_ports = engine.suggest("ports", max_results=6)
    assert any("What ports are open" in s.text for s in suggs_ports)


def test_multi_token_strict_filtering():
    """Tests that queries with multiple words strictly require all meaningful keywords."""
    engine = AutocompleteEngine()

    # 'open browser' should strictly match browser items, not port items that happen to contain 'open'
    suggs = engine.suggest("open browser", max_results=10)
    for s in suggs:
        lower_text = s.text.lower()
        lower_desc = s.description.lower()
        # Must relate to browser or chrome/firefox/brave
        assert any(k in lower_text or k in lower_desc for k in ["browser", "chrome", "firefox", "brave", "web", "internet"])

