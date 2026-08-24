"""Natural Language Processing layer — intent classification, context memory, and ambiguity resolution."""

from ops_assistant.nlp.intent_router import IntentRouter, Intent, IntentType
from ops_assistant.nlp.context_manager import ContextManager, ConversationTurn
from ops_assistant.nlp.ambiguity_resolver import AmbiguityResolver, AmbiguityResolution
from ops_assistant.nlp.synonym_dict import SynonymDictionary
from ops_assistant.nlp.entity_extractor import EntityExtractor, ExtractedEntities

__all__ = [
    "IntentRouter",
    "Intent",
    "IntentType",
    "ContextManager",
    "ConversationTurn",
    "AmbiguityResolver",
    "AmbiguityResolution",
    "SynonymDictionary",
    "EntityExtractor",
]
