#!/usr/bin/env python3
"""Test ECOTerm ontology search using DatabaseMethods.

ECOTerm - Evidence & Conclusion Ontology
Record count: 2,125 records
Test terms: "evidence", "experimental", "computational"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestECOTerm(unittest.TestCase):
    """Test ECOTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'ECOTerm'

    def test_exact_match_evidence(self):
        """Test exact match search for 'evidence'."""
        results = self.db.search_ontology_terms(
            term='evidence',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "evidence" in the name (case-insensitive)
            self.assertIn('evidence', result.name.lower())

    def test_prefix_match_experimental(self):
        """Test prefix match search for 'experimental'."""
        results = self.db.search_ontology_terms(
            term='experimental',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find experimental-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_computational(self):
        """Test contains match search for 'computational'."""
        results = self.db.search_ontology_terms(
            term='computational',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find computational-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='assay',
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
            term='evidence',
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
