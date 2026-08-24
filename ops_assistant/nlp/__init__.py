"""Natural Language Processing layer — intent classification, context memory, and ambiguity resolution."""

from ops_assistant.nlp.intent_router import IntentRouter, Intent, IntentType
from ops_assistant.nlp.context_manager import ContextManager, ConversationTurn
from ops_assistant.nlp.ambiguity_resolver import AmbiguityResolver, AmbiguityResolution
from ops_assistant.nlp.synonym_dict import SynonymDictionary
from ops_assistant.nlp.entity_extractor import EntityExtractor, ExtractedEntities
from ops_assistant.nlp.autocomplete import AutocompleteEngine, Suggestion, get_autocomplete_engine
from ops_assistant.nlp.fuzzy_matcher import FuzzyEntityMatcher, SymSpellMatcher, damerau_levenshtein_distance, CorrectionResult

from ops_assistant.nlp.intent_chain import IntentChainEngine, CompoundIntent, ChainStep, ChainContext, CompoundQuerySplitter

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
    "AutocompleteEngine",
    "Suggestion",
    "get_autocomplete_engine",
    "FuzzyEntityMatcher",
    "SymSpellMatcher",
    "damerau_levenshtein_distance",
    "CorrectionResult",
    "IntentChainEngine",
    "CompoundIntent",
    "ChainStep",
    "ChainContext",
    "CompoundQuerySplitter",
]
