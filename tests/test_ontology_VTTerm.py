#!/usr/bin/env python3
"""Test VTTerm (Vertebrate Trait Ontology) ontology type.

VTTerm: Vertebrate Trait Ontology
Record count: 3,897 records
Test terms: "trait", "body", "weight"
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


class TestVTTermOntology(unittest.TestCase):
    """Test VTTerm ontology type using unified ontologyterm table."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()
        cls.ontology_type = 'VTTerm'

    def test_search_trait(self):
        """Test search for 'trait' in VTTerm."""
        results = self.db.search_ontology_terms(
            term='trait',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'trait'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)
        self.assertIsNotNone(result.curie)
        self.assertIsNotNone(result.name)

        print(f"\n✅ VTTerm 'trait': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_body(self):
        """Test search for 'body' in VTTerm."""
        results = self.db.search_ontology_terms(
            term='body',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'body'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ VTTerm 'body': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_search_weight(self):
        """Test search for 'weight' in VTTerm."""
        results = self.db.search_ontology_terms(
            term='weight',
            ontology_type=self.ontology_type,
            limit=5
        )

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0, "Should find results for 'weight'")

        # Validate first result
        result = results[0]
        self.assertIsInstance(result, OntologyTermResult)
        self.assertEqual(result.ontology_type, self.ontology_type)

        print(f"\n✅ VTTerm 'weight': Found {len(results)} results")
        print(f"   Sample: {result.curie} - {result.name}")

    def test_synonym_search(self):
        """Test synonym search for VTTerm."""
        results_with_syn = self.db.search_ontology_terms(
            term='trait',
            ontology_type=self.ontology_type,
            include_synonyms=True,
            limit=5
        )

        results_without_syn = self.db.search_ontology_terms(
            term='trait',
            ontology_type=self.ontology_type,
            include_synonyms=False,
            limit=5
        )

        self.assertIsInstance(results_with_syn, list)
        self.assertIsInstance(results_without_syn, list)

        print(f"\n✅ VTTerm synonym search: "
              f"with_syn={len(results_with_syn)}, "
              f"without_syn={len(results_without_syn)}")

    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match for VTTerm."""
        exact_results = self.db.search_ontology_terms(
            term='weight',
            ontology_type=self.ontology_type,
            exact_match=True,
            limit=5
        )

        partial_results = self.db.search_ontology_terms(
            term='weight',
            ontology_type=self.ontology_type,
            exact_match=False,
            limit=5
        )

        self.assertIsInstance(exact_results, list)
        self.assertIsInstance(partial_results, list)

        print(f"\n✅ VTTerm exact vs partial: "
              f"exact={len(exact_results)}, "
              f"partial={len(partial_results)}")


if __name__ == '__main__':
    unittest.main(verbosity=2)
