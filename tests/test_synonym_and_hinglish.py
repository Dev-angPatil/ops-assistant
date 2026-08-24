"""
Unit Tests for Synonym Dictionary and Diverse Phrasing.
"""

from ops_assistant.nlp.synonym_dict import SynonymDictionary
from ops_assistant.agent import OpsAssistantAgent


def test_synonym_dictionary_cpu_variations():
    queries = [
        "show CPU usage",
        "How much CPU is being used?",
        "check processor usage",
        "Is my processor busy?",
        "tell me current CPU load"
    ]
    for q in queries:
        cat, conf = SynonymDictionary.normalize_query_intent(q)
        assert "CPU" in cat
        assert conf >= 0.90


def test_synonym_dictionary_ram_variations():
    queries = [
        "how much ram is used",
        "check memory",
        "physical memory usage"
    ]
    for q in queries:
        cat, conf = SynonymDictionary.normalize_query_intent(q)
        assert "RAM" in cat
        assert conf >= 0.90


def test_agent_diverse_phrasing_execution():
    agent = OpsAssistantAgent()

    # Phrasing variations for folder creation
    f1 = agent.execute_agent_action("Create a folder called Projects", execute=False)
    assert f1.get("command") == "mkdir -p 'Projects'"

    # Phrasing variations for browser
    b1 = agent.execute_agent_action("Open Firefox", execute=False)
    assert "firefox" in b1.get("command").lower()

    # Phrasing variations for web search
    s1 = agent.execute_agent_action("Search for Python tutorials", execute=False)
    assert "google.com/search" in s1.get("command")
    assert "Python+tutorials" in s1.get("command")

    # Clean temp files
    c1 = agent.execute_agent_action("Delete temporary files", execute=False)
    assert "rm -rf /tmp/*" in c1.get("command")
