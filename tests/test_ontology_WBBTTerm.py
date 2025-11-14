#!/usr/bin/env python3
"""Test WBBTTerm (C. elegans Anatomy) ontology type.

WBBTTerm: C. elegans Anatomy Ontology
Record count: 6,762 records
Test terms: "cell", "pharynx", "intestine"
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestWBBTTermOntology(unittest.TestCase):
    """Test WBBTTerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'WBBTTerm'

    def test_search_cell(self):
        """Test search for 'cell' in WBBTTerm."""
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
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)

        print(f"\n✅ WBBTTerm 'cell': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_pharynx(self):
        """Test search for 'pharynx' in WBBTTerm."""
        results = self.db.search_ontology_terms(
            term='pharynx',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'pharynx'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ WBBTTerm 'pharynx': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_intestine(self):
        """Test search for 'intestine' in WBBTTerm."""
        results = self.db.search_ontology_terms(
            term='intestine',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'intestine'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ WBBTTerm 'intestine': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_synonym_search(self):
        """Test synonym search for WBBTTerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='cell',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='cell',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)

        print(f"\n✅ WBBTTerm synonym search: "
              f"with_syn={len(results_with_syn)}, "
              f"without_syn={len(results_without_syn)}")

    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for WBBTTerm."""
        exact_results = self.db.search_ontology_terms(
            term='pharynx',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='pharynx',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)

        print(f"\n✅ WBBTTerm exact vs partial: "
              f"exact={len(exact_results)}, "
              f"partial={len(partial_results)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
