#!/usr/bin/env python3
"""Test CLTerm (Cell Ontology) ontology type.

CLTerm: Cell Ontology
Record count: 3,129 records
Test terms: "cell", "neuron", "fibroblast"
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestCLTermOntology(unittest.TestCase):
    """Test CLTerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'CLTerm'

    def test_search_cell(self):
        """Test search for 'cell' in CLTerm."""
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

        print(f"\n✅ CLTerm 'cell': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_neuron(self):
        """Test search for 'neuron' in CLTerm."""
        results = self.db.search_ontology_terms(
            term='neuron',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'neuron'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ CLTerm 'neuron': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_fibroblast(self):
        """Test search for 'fibroblast' in CLTerm."""
        results = self.db.search_ontology_terms(
            term='fibroblast',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'fibroblast'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ CLTerm 'fibroblast': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_synonym_search(self):
        """Test synonym search for CLTerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='neuron',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='neuron',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)

        print(f"\n✅ CLTerm synonym search: "
              f"with_syn={len(results_with_syn)}, "
              f"without_syn={len(results_without_syn)}")

    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for CLTerm."""
        exact_results = self.db.search_ontology_terms(
            term='neuron',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='neuron',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)

        print(f"\n✅ CLTerm exact vs partial: "
              f"exact={len(exact_results)}, "
              f"partial={len(partial_results)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
