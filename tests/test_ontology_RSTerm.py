#!/usr/bin/env python3
"""Test RSTerm (Rat Strain Ontology) ontology type.

RSTerm: Rat Strain Ontology
Record count: 5,443 records
Test terms: "rat", "strain", "Wistar"
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestRSTermOntology(unittest.TestCase):
    """Test RSTerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'RSTerm'

    def test_search_rat(self):
        """Test search for 'rat' in RSTerm."""
        results = self.db.search_ontology_terms(
            term='rat',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'rat'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)

        print(f"\n✅ RSTerm 'rat': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_strain(self):
        """Test search for 'strain' in RSTerm."""
        results = self.db.search_ontology_terms(
            term='strain',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'strain'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ RSTerm 'strain': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_wistar(self):
        """Test search for 'Wistar' in RSTerm."""
        results = self.db.search_ontology_terms(
            term='Wistar',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'Wistar'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ RSTerm 'Wistar': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_synonym_search(self):
        """Test synonym search for RSTerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='rat',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='rat',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)

        print(f"\n✅ RSTerm synonym search: "
              f"with_syn={len(results_with_syn)}, "
              f"without_syn={len(results_without_syn)}")

    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for RSTerm."""
        exact_results = self.db.search_ontology_terms(
            term='Wistar',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='Wistar',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)

        print(f"\n✅ RSTerm exact vs partial: "
              f"exact={len(exact_results)}, "
              f"partial={len(partial_results)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
