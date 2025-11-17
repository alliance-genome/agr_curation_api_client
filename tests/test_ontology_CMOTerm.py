#!/usr/bin/env python3
"""Test CMOTerm (Clinical Measurement Ontology) ontology type.

CMOTerm: Clinical Measurement Ontology
Record count: 4,039 records
Test terms: "measurement", "blood", "pressure"
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


@unittest.skipUnless(os.getenv('PERSISTENT_STORE_DB_HOST'),
                     "Database integration tests require PERSISTENT_STORE_DB_* environment variables")
class TestCMOTermOntology(unittest.TestCase):
    """Test CMOTerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'CMOTerm'

    def test_search_measurement(self):
        """Test search for 'measurement' in CMOTerm."""
        results = self.db.search_ontology_terms(
            term='measurement',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'measurement'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)


    def test_search_blood(self):
        """Test search for 'blood' in CMOTerm."""
        results = self.db.search_ontology_terms(
            term='blood',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'blood'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_search_pressure(self):
        """Test search for 'pressure' in CMOTerm."""
        results = self.db.search_ontology_terms(
            term='pressure',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'pressure'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_synonym_search(self):
        """Test synonym search for CMOTerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='blood',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='blood',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)


    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for CMOTerm."""
        exact_results = self.db.search_ontology_terms(
            term='pressure',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='pressure',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)



if __name__ == '__main__':
    unittest.main(verbosity=2)
