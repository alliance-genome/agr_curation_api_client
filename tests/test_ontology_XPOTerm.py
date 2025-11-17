#!/usr/bin/env python3
"""Test XPOTerm ontology search using DatabaseMethods.

XPOTerm - Xenopus Phenotype Ontology
Record count: 21,197 records
Test terms: "lethal", "abnormal", "morphology"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


@unittest.skipUnless(os.getenv('PERSISTENT_STORE_DB_HOST'),
                     "Database integration tests require PERSISTENT_STORE_DB_* environment variables")
class TestXPOTerm(unittest.TestCase):
    """Test XPOTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'XPOTerm'

    def test_exact_match_lethal(self):
        """Test exact match search for 'lethal'."""
        results = self.db.search_ontology_terms(
            term='lethal',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_prefix_match_abnormal(self):
        """Test prefix match search for 'abnormal'."""
        results = self.db.search_ontology_terms(
            term='abnormal',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find abnormal-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_morphology(self):
        """Test contains match search for 'morphology'."""
        results = self.db.search_ontology_terms(
            term='morphology',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find morphology-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='death',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        # May or may not have results, just verify structure
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_result_structure(self):
        """Test that results have expected structure."""
        results = self.db.search_ontology_terms(
            term='lethal',
            ontology_type=self.ontology_type,
            limit=1
        )
        if results:
            result = results[0]
            self.assertIsNotNone(result.curie)
            self.assertIsNotNone(result.name)
            self.assertIsNotNone(result.namespace)
            self.assertEqual(result.ontology_type, self.ontology_type)
            self.assertIsInstance(result.synonyms, list)


if __name__ == '__main__':
    unittest.main(verbosity=2)
