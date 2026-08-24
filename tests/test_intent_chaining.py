"""
Unit and Integration Tests for Compound & Multi-Step Natural Language Intent Chaining.
"""

import unittest
from ops_assistant.nlp.intent_chain import (
    ChainStep, CompoundIntent, ChainContext, CompoundQuerySplitter, IntentChainEngine
)
from ops_assistant.nlp.intent_router import IntentRouter, IntentType
from ops_assistant.agent.core import ReActAgent


class TestIntentChaining(unittest.TestCase):
    """Tests for CompoundQuerySplitter, ChainContext, IntentChainEngine, and ReActAgent Integration."""

    def test_compound_query_splitter_detection(self):
        # Explicit connectives
        self.assertTrue(CompoundQuerySplitter.is_compound("stop nginx and then restart apache"))
        self.assertTrue(CompoundQuerySplitter.is_compound("create folder /tmp/app; touch /tmp/app/main.py"))
        self.assertTrue(CompoundQuerySplitter.is_compound("clean trash, check RAM usage, and show open ports"))

        # Compound noun phrases should NOT be split into separate intents
        self.assertFalse(CompoundQuerySplitter.is_compound("status of nginx and apache"))

    def test_compound_query_splitter_clauses(self):
        q1 = "create folder /tmp/test, then create file config.json in it, and make it executable"
        clauses1 = CompoundQuerySplitter.split_query(q1)
        self.assertEqual(len(clauses1), 3)
        self.assertIn("create folder /tmp/test", clauses1[0])
        self.assertIn("create file config.json in it", clauses1[1])
        self.assertIn("make it executable", clauses1[2])

        q2 = "clean trash, check RAM usage, and show listening ports"
        clauses2 = CompoundQuerySplitter.split_query(q2)
        self.assertEqual(len(clauses2), 3)
        self.assertIn("clean trash", clauses2[0])
        self.assertIn("check RAM usage", clauses2[1])
        self.assertIn("show listening ports", clauses2[2])

    def test_chain_context_pronoun_resolution(self):
        ctx = ChainContext()
        ctx.last_target_path = "/tmp/my_project"
        ctx.last_file_path = "/tmp/my_project/app.py"

        # Resolve "in it"
        res1 = ctx.resolve_clause("create file notes.txt in it")
        self.assertEqual(res1, "create file notes.txt inside /tmp/my_project")

        # Resolve "make it executable"
        res2 = ctx.resolve_clause("make it executable")
        self.assertEqual(res2, "make /tmp/my_project/app.py executable")

        # Resolve service "it"
        ctx.last_service = "nginx"
        res3 = ctx.resolve_clause("restart it")
        self.assertEqual(res3, "restart nginx")

    def test_intent_chain_engine_synthesis(self):
        engine = IntentChainEngine()
        query = "create folder /tmp/chain_demo and touch /tmp/chain_demo/test.txt"

        result = engine.process(query)
        self.assertIsInstance(result, CompoundIntent)
        self.assertTrue(result.is_compound)
        self.assertEqual(len(result.steps), 2)

        # Check chained command
        self.assertIn("mkdir -p '/tmp/chain_demo'", result.chained_command)
        self.assertIn("touch /tmp/chain_demo/test.txt", result.chained_command)
        self.assertIn("&&", result.chained_command)

        # Check rollback synthesis (reverse execution order)
        self.assertIsNotNone(result.chained_rollback)
        self.assertIn("rm -f '/tmp/chain_demo/test.txt'", result.chained_rollback)

    def test_intent_router_route_compound(self):
        router = IntentRouter()
        res = router.route_compound("stop nginx and restart apache")
        self.assertIsInstance(res, CompoundIntent)
        self.assertEqual(len(res.steps), 2)
        self.assertEqual(res.steps[0].intent.type, IntentType.SERVICE_STOP)
        self.assertEqual(res.steps[1].intent.type, IntentType.SERVICE_RESTART)

    def test_react_agent_execute_compound_action(self):
        agent = ReActAgent(llm_provider=None)
        action = agent.execute_agent_action(
            "create folder /tmp/agent_chain and create file /tmp/agent_chain/hello.py with content 'print(123)'",
            execute=False
        )

        self.assertEqual(action["intent"], "compound_intent")
        self.assertTrue(action["is_compound"])
        self.assertEqual(action["total_steps"], 2)
        self.assertIn("mkdir -p '/tmp/agent_chain'", action["command"])
        self.assertIn("echo 'print(123)' > '/tmp/agent_chain/hello.py'", action["command"])
        self.assertEqual(len(action["planned_commands"]), 2)
        self.assertIsNotNone(action["rollback_command"])


if __name__ == "__main__":
    unittest.main()
