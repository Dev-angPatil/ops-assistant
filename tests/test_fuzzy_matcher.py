"""
Unit tests for Fuzzy Entity Matching & Spell Correction Engine.
"""

import unittest
from ops_assistant.nlp.fuzzy_matcher import (
    damerau_levenshtein_distance,
    SymSpellMatcher,
    SystemEntityCollector,
    FuzzyEntityMatcher,
    CorrectionResult
)
from ops_assistant.nlp.intent_router import IntentRouter, IntentType


class TestFuzzyMatcher(unittest.TestCase):
    """Tests for Damerau-Levenshtein, SymSpell, System Entity Collection, and Intent Routing."""

    def test_damerau_levenshtein_distance(self):
        # Exact match
        self.assertEqual(damerau_levenshtein_distance("restart", "restart"), 0)
        
        # Transposition of adjacent characters (a <-> t)
        self.assertEqual(damerau_levenshtein_distance("resatrt", "restart"), 1)
        
        # Deletion (missing 'i')
        self.assertEqual(damerau_levenshtein_distance("ngnx", "nginx"), 1)
        
        # Transposition (u <-> t)
        self.assertEqual(damerau_levenshtein_distance("stauts", "status"), 1)
        
        # Substitutions
        self.assertEqual(damerau_levenshtein_distance("ckick", "check"), 2)
        
        # Empty string cases
        self.assertEqual(damerau_levenshtein_distance("", "test"), 4)
        self.assertEqual(damerau_levenshtein_distance("test", ""), 4)

    def test_symspell_matcher(self):
        matcher = SymSpellMatcher(max_edit_distance=2)
        matcher.add_words(["restart", "status", "check", "nginx", "ufw"], category="ops")

        # Lookup exact
        self.assertEqual(matcher.lookup("restart")[0][0], "restart")

        # Lookup transposition typo
        res = matcher.lookup("resatrt")
        self.assertTrue(len(res) > 0)
        self.assertEqual(res[0][0], "restart")
        self.assertEqual(res[0][1], 1)

        # Lookup typo for nginx
        res_nginx = matcher.lookup("ngnx")
        self.assertTrue(len(res_nginx) > 0)
        self.assertEqual(res_nginx[0][0], "nginx")

    def test_system_entity_collector(self):
        pkgs = SystemEntityCollector.get_installed_packages()
        units = SystemEntityCollector.get_systemd_units()
        mounts = SystemEntityCollector.get_mounted_paths()
        ifaces = SystemEntityCollector.get_network_interfaces()

        self.assertIsInstance(pkgs, list)
        self.assertTrue(len(pkgs) > 0)
        self.assertIsInstance(units, list)
        self.assertTrue(len(units) > 0)
        self.assertIsInstance(mounts, list)
        self.assertTrue(len(mounts) > 0)
        self.assertIsInstance(ifaces, list)
        self.assertTrue(len(ifaces) > 0)

    def test_fuzzy_entity_matcher_query_correction(self):
        matcher = FuzzyEntityMatcher.get_instance()

        # Test case 1: "resatrt ngnx" -> "restart nginx"
        res1 = matcher.correct_query("resatrt ngnx")
        self.assertEqual(res1.corrected_query.lower(), "restart nginx")
        self.assertTrue(len(res1.replacements) >= 2)

        # Test case 2: "ckick ufw stauts" -> "check ufw status"
        res2 = matcher.correct_query("ckick ufw stauts")
        self.assertEqual(res2.corrected_query.lower(), "check ufw status")
        self.assertTrue(len(res2.replacements) >= 2)

        # Test case 3: Exact valid query unchanged
        res3 = matcher.correct_query("restart nginx")
        self.assertEqual(res3.corrected_query, "restart nginx")
        self.assertEqual(len(res3.replacements), 0)

    def test_intent_router_spell_correction_integration(self):
        router = IntentRouter()

        # Test typo: "resatrt ngnx" -> SERVICE_RESTART intent with service='nginx'
        intent1 = router.classify("resatrt ngnx")
        self.assertEqual(intent1.type, IntentType.SERVICE_RESTART)
        self.assertEqual(intent1.args.get("service"), "nginx")
        self.assertIsNotNone(intent1.corrected_query)
        self.assertTrue(len(intent1.corrections) > 0)

        # Test typo: "ckick ufw stauts" -> FIREWALL_STATUS or SERVICE_STATUS intent
        intent2 = router.classify("ckick ufw stauts")
        self.assertIn(intent2.type, (IntentType.FIREWALL_STATUS, IntentType.SERVICE_STATUS))
        self.assertIsNotNone(intent2.corrected_query)
        self.assertTrue(len(intent2.corrections) > 0)

    def test_additional_entity_typos(self):
        matcher = FuzzyEntityMatcher.get_instance()

        # Systemd unit typo: "ststus docker" -> "status docker"
        r1 = matcher.correct_query("ststus docker")
        self.assertEqual(r1.corrected_query.lower(), "status docker")

        # Mount path typo: "munt /dev/sdb1" -> "mount /dev/sdb1"
        r2 = matcher.correct_query("munt /dev/sdb1")
        self.assertEqual(r2.corrected_query.lower(), "mount /dev/sdb1")

        # Network interface typo: "show netwrk interface" -> "show network interface"
        r3 = matcher.correct_query("show netwrk interface")
        self.assertEqual(r3.corrected_query.lower(), "show network interface")


if __name__ == "__main__":
    unittest.main()
