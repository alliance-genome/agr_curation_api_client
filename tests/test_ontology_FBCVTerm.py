#!/usr/bin/env python3
"""Test FBCVTerm ontology search using DatabaseMethods.

FBCVTerm - FlyBase Controlled Vocabulary
Record count: 1,197 records
Test terms: "wing", "cell", "tissue"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestFBCVTerm(unittest.TestCase):
    """Test FBCVTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'FBCVTerm'

    def test_exact_match_wing(self):
        """Test exact match search for 'wing'."""
        results = self.db.search_ontology_terms(
            term='wing',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "wing" in the name (case-insensitive)
            self.assertIn('wing', result.name.lower())

    def test_prefix_match_cell(self):
        """Test prefix match search for 'cell'."""
        results = self.db.search_ontology_terms(
            term='cell',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find cell-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_tissue(self):
        """Test contains match search for 'tissue'."""
        results = self.db.search_ontology_terms(
            term='tissue',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find tissue-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='phenotype',
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
            term='wing',
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
