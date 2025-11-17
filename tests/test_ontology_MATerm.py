#!/usr/bin/env python3
"""Test MATerm (Mouse Adult Anatomy Ontology) ontology type.

MATerm: Mouse Adult Anatomy Ontology
Record count: 3,230 records
Test terms: "brain", "tissue", "cell"
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
class TestMATermOntology(unittest.TestCase):
    """Test MATerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'MATerm'

    def test_search_brain(self):
        """Test search for 'brain' in MATerm."""
        results = self.db.search_ontology_terms(
            term='brain',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'brain'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)


    def test_search_tissue(self):
        """Test search for 'tissue' in MATerm."""
        results = self.db.search_ontology_terms(
            term='tissue',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'tissue'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_search_cell(self):
        """Test search for 'cell' in MATerm."""
        results = self.db.search_ontology_terms(
            term='cell',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'cell'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)


    def test_synonym_search(self):
        """Test synonym search for MATerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='brain',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='brain',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)


    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for MATerm."""
        exact_results = self.db.search_ontology_terms(
            term='brain',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='brain',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)



if __name__ == '__main__':
    unittest.main(verbosity=2)
