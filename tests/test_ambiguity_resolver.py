"""
Unit Tests for Ambiguity Resolver.
"""

from ops_assistant.nlp.ambiguity_resolver import AmbiguityResolver
from ops_assistant.agent import OpsAssistantAgent


def test_ambiguity_missing_move_file():
    res = AmbiguityResolver.check_ambiguity("move the file")
    assert res.is_ambiguous is True
    assert res.ambiguity_type == "missing_entity"
    assert "Which file" in res.prompt


def test_ambiguity_missing_open_doc():
    res = AmbiguityResolver.check_ambiguity("open the document")
    assert res.is_ambiguous is True
    assert "Which document" in res.prompt


def test_ambiguity_low_confidence_voice():
    res = AmbiguityResolver.check_ambiguity("delete project", confidence=0.55)
    assert res.is_ambiguous is True
    assert res.ambiguity_type == "low_confidence_voice"
    assert "I heard:" in res.prompt


def test_ambiguity_agent_dispatch():
    agent = OpsAssistantAgent()
    act = agent.execute_agent_action("move the file", execute=False)
    assert act.get("is_ambiguous") is True
    assert act.get("intent") == "clarification_needed"
    assert act.get("command") == ""
