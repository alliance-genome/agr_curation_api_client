#!/usr/bin/env python3
"""Test XSMOTerm ontology search using DatabaseMethods.

XSMOTerm - Cross-Species Molecule Ontology
Record count: 444 records
Test terms: "chemical", "molecule", "compound"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


@unittest.skipUnless(os.getenv('PERSISTENT_STORE_DB_HOST'),
                     "Database integration tests require PERSISTENT_STORE_DB_* environment variables")
class TestXSMOTerm(unittest.TestCase):
    """Test XSMOTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'XSMOTerm'

    def test_exact_match_chemical(self):
        """Test exact match search for 'chemical'."""
        results = self.db.search_ontology_terms(
            term='chemical',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "chemical" in the name (case-insensitive)
            self.assertIn('chemical', result.name.lower())

    def test_prefix_match_a(self):
        """Test prefix match search for 'a'."""
        results = self.db.search_ontology_terms(
            term='a',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find a-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_compound(self):
        """Test contains match search for 'compound'."""
        results = self.db.search_ontology_terms(
            term='compound',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find compound-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='substance',
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
            term='chemical',
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
