#!/usr/bin/env python3
"""Test BSPOTerm ontology search using DatabaseMethods.

BSPOTerm - Biological Spatial Ontology
Record count: 139 records
Test terms: "dorsal", "anterior", "posterior"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestBSPOTerm(unittest.TestCase):
    """Test BSPOTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'BSPOTerm'

    def test_exact_match_dorsal(self):
        """Test exact match search for 'dorsal'."""
        results = self.db.search_ontology_terms(
            term='dorsal',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "dorsal" in the name (case-insensitive)
            self.assertIn('dorsal', result.name.lower())

    def test_prefix_match_anterior(self):
        """Test prefix match search for 'anterior'."""
        results = self.db.search_ontology_terms(
            term='anterior',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find anterior-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_posterior(self):
        """Test contains match search for 'posterior'."""
        results = self.db.search_ontology_terms(
            term='posterior',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find posterior-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='lateral',
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
            term='dorsal',
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
