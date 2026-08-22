"""AI-Powered Linux Operations Assistant Agent Subsystem."""

from ops_assistant.models import SafetyLevel
from ops_assistant.agent.tools_registry import AgentToolsRegistry, AgentTool
from ops_assistant.agent.providers import (
    LLMProvider,
    GeminiProvider,
    OllamaProvider,
    LlamaCppProvider
)
from ops_assistant.agent.core import ReActAgent
from ops_assistant.agent.session import ConversationSession, ConversationTurn

# Expose OpsAssistantAgent as the primary entrypoint for CLI, GUI, and API clients
OpsAssistantAgent = ReActAgent

__all__ = [
    "OpsAssistantAgent",
    "ReActAgent",
    "ConversationSession",
    "ConversationTurn",
    "LLMProvider",
    "GeminiProvider",
    "OllamaProvider",
    "LlamaCppProvider",
    "SafetyLevel",
    "AgentToolsRegistry",
    "AgentTool"
]

