#!/usr/bin/env python3
"""Test MMUSDVTerm ontology search using DatabaseMethods.

MMUSDVTerm - Mouse Developmental Stages Ontology
Record count: 134 records
Test terms: "embryonic", "postnatal", "stage"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestMMUSDVTerm(unittest.TestCase):
    """Test MMUSDVTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'MMUSDVTerm'

    def test_exact_match_embryonic(self):
        """Test exact match search for 'embryonic'."""
        results = self.db.search_ontology_terms(
            term='embryonic',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "embryonic" in the name (case-insensitive)
            self.assertIn('embryonic', result.name.lower())

    def test_prefix_match_postnatal(self):
        """Test prefix match search for 'postnatal'."""
        results = self.db.search_ontology_terms(
            term='postnatal',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find postnatal-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_stage(self):
        """Test contains match search for 'stage'."""
        results = self.db.search_ontology_terms(
            term='stage',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find stage-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='mouse',
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
            term='embryonic',
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
