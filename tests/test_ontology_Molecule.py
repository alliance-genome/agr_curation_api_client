#!/usr/bin/env python3
"""Test Molecule ontology type.

Molecule: Molecule entities
Record count: 3,782 records
Test terms: "protein", "molecule", "0"
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
class TestMoleculeOntology(unittest.TestCase):
    """Test Molecule ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'Molecule'

    def test_search_protein(self):
        """Test search for 'protein' in Molecule."""
        results = self.db.search_ontology_terms(
            term='protein',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'protein'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)


    def test_search_molecule(self):
        """Test search for 'molecule' in Molecule."""
        results = self.db.search_ontology_terms(
            term='molecule',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'molecule'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_search_zero(self):
        """Test search for '0' in Molecule."""
        results = self.db.search_ontology_terms(
            term='0',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for '0'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_synonym_search(self):
        """Test synonym search for Molecule."""
        results_with_syn = self.db.search_ontology_terms(
            term='protein',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='protein',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)


    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for Molecule."""
        exact_results = self.db.search_ontology_terms(
            term='protein',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='protein',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)



if __name__ == '__main__':
    unittest.main(verbosity=2)
