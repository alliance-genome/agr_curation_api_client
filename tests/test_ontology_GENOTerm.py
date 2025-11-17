#!/usr/bin/env python3
"""Test GENOTerm ontology search using DatabaseMethods.

GENOTerm - Genotype Ontology
Record count: 222 records
Test terms: "genotype", "allele", "zygosity"
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


@unittest.skipUnless(os.getenv('PERSISTENT_STORE_DB_HOST'),
                     "Database integration tests require PERSISTENT_STORE_DB_* environment variables")
class TestGENOTerm(unittest.TestCase):
    """Test GENOTerm searches using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseMethods()
        cls.ontology_type = 'GENOTerm'

    def test_exact_match_genotype(self):
        """Test exact match search for 'genotype'."""
        results = self.db.search_ontology_terms(
            term='genotype',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, OntologyTermResult)
            self.assertEqual(result.ontology_type, self.ontology_type)
            # Exact match should have "genotype" in the name (case-insensitive)
            self.assertIn('genotype', result.name.lower())

    def test_prefix_match_allele(self):
        """Test prefix match search for 'allele'."""
        results = self.db.search_ontology_terms(
            term='allele',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find allele-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_contains_match_zygosity(self):
        """Test contains match search for 'zygosity'."""
        results = self.db.search_ontology_terms(
            term='zygosity',
            ontology_type=self.ontology_type,
            limit=10
        )
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find zygosity-related results")
        for result in results:
            self.assertEqual(result.ontology_type, self.ontology_type)

    def test_synonym_matching(self):
        """Test synonym search."""
        results = self.db.search_ontology_terms(
            term='variant',
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
            term='genotype',
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
