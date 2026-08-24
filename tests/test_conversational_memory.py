"""
Unit Tests for Conversational Memory and Context Manager.
"""

import os
from ops_assistant.nlp.context_manager import ContextManager
from ops_assistant.agent import OpsAssistantAgent


def test_context_manager_state_tracking():
    ctx = ContextManager()
    downloads_path = os.path.expanduser("~/Downloads")
    ctx.update_context(
        query="open downloads",
        intent="desktop_open_folder",
        command=f"xdg-open '{downloads_path}'",
        target_path=downloads_path,
        output_summary="Opened ~/Downloads"
    )

    assert ctx.active_directory == downloads_path
    assert len(ctx.turns) == 1


def test_context_manager_anaphora_largest_file():
    ctx = ContextManager()
    downloads_path = os.path.expanduser("~/Downloads")
    ctx.update_context(
        query="open downloads",
        intent="desktop_open_folder",
        command=f"xdg-open '{downloads_path}'",
        target_path=downloads_path
    )

    resolved, meta = ctx.resolve_contextual_query("delete the largest file")
    assert meta["resolved_from_context"] is True
    assert "largest file" in resolved
    assert downloads_path in resolved


def test_context_manager_service_followup():
    ctx = ContextManager()
    ctx.update_context(
        query="why is nginx failing",
        intent="diagnose",
        service_name="nginx"
    )

    resolved, meta = ctx.resolve_contextual_query("restart it")
    assert meta["resolved_from_context"] is True
    assert resolved == "restart nginx"


def test_agent_multi_turn_execution():
    agent = OpsAssistantAgent()
    t1 = agent.execute_agent_action("open downloads", execute=False)
    assert t1.get("command") is not None
    assert agent.context_manager.active_directory == os.path.expanduser("~/Downloads")

    t2 = agent.execute_agent_action("delete the largest file", execute=False)
    assert t2.get("command") is not None
    assert "Downloads" in t2.get("command")
    assert t2.get("safety_level") == "HIGH_RISK"
