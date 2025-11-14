#!/usr/bin/env python3
"""Test NCBITaxonTerm ontology search using DatabaseMethods.

NCBITaxonTerm - NCBI Taxonomy
Record count: 1,715 records
Test terms: "elegans", "melanogaster", "sapiens"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestNCBITaxonTerm(unittest.TestCase):
    """Test NCBITaxonTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'NCBITaxonTerm'

    def test_exact_match_elegans(self):
        """Test exact match search for 'elegans'."""
        results = self.db.search_ontology_terms(
            term='elegans',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "elegans" in the name (case-insensitive)
            self.assertIn('elegans', result.name.lower())

    def test_prefix_match_melanogaster(self):
        """Test prefix match search for 'melanogaster'."""
        results = self.db.search_ontology_terms(
            term='melanogaster',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find melanogaster-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_sapiens(self):
        """Test contains match search for 'sapiens'."""
        results = self.db.search_ontology_terms(
            term='sapiens',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find sapiens-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='human',
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
            term='elegans',
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
