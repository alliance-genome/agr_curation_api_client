#!/usr/bin/env python3
"""Comprehensive test of all 45 ontology types using DatabaseMethods.

This test validates that all ontology types in the production database
can be searched using the search_ontology_terms() method.
"""

import unittest
import os

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


@unittest.skipUnless(
    os.getenv("PERSISTENT_STORE_DB_HOST"),
    "Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)
class TestAllOntologyTypes(unittest.TestCase):
    """Test all 45 ontology types against production database."""

    # All 45 ontology types found in production database
    # (from query: SELECT DISTINCT ontologytermtype FROM ontologyterm)
    ALL_ONTOLOGY_TYPES = [
        "APOTerm",  # Ascomycete Phenotype (309 records)
        "ATPTerm",  # Alliance Phenotype (334 records)
        "BSPOTerm",  # Biological Spatial (139 records)
        "BTOTerm",  # BRENDA Tissue (6,511 records)
        "CHEBITerm",  # Chemical Entities (204,377 records - LARGEST!)
        "CLTerm",  # Cell Ontology (3,129 records)
        "CMOTerm",  # Clinical Measurement (4,039 records)
        "DAOTerm",  # Disease Anatomy (27,076 records)
        "DOTerm",  # Disease Ontology (11,946 records)
        "ECOTerm",  # Evidence & Conclusion (2,125 records)
        "EMAPATerm",  # Mouse Developmental Anatomy (7,990 records)
        "FBCVTerm",  # FlyBase Controlled Vocabulary (1,197 records)
        "FBDVTerm",  # FlyBase Development (210 records)
        "GENOTerm",  # Genotype Ontology (222 records)
        "GOTerm",  # Gene Ontology (39,906 records)
        "HPTerm",  # Human Phenotype (19,232 records)
        "MATerm",  # Mouse Adult Anatomy (3,230 records)
        "MITerm",  # Molecular Interactions (1,467 records)
        "MMOTerm",  # Measurement Method (850 records)
        "MMUSDVTerm",  # Mouse Development (134 records)
        "MODTerm",  # Model Organism Database (1,978 records)
        "Molecule",  # Molecule entities (3,782 records)
        "MPATHTerm",  # Mouse Pathology (841 records)
        "MPTerm",  # Mammalian Phenotype (14,451 records)
        "NCBITaxonTerm",  # NCBI Taxonomy (1,715 records)
        "OBITerm",  # Biomedical Investigations (4,072 records)
        "PATOTerm",  # Phenotypic Quality (1,887 records)
        "PWTerm",  # Pathway Ontology (2,705 records)
        "ROTerm",  # Relation Ontology (664 records)
        "RSTerm",  # Rat Strain (5,443 records)
        "SOTerm",  # Sequence Ontology (2,404 records)
        "UBERONTerm",  # Cross-species Anatomy (14,668 records)
        "VTTerm",  # Vertebrate Trait (3,897 records)
        "WBBTTerm",  # C. elegans Anatomy (6,762 records)
        "WBLSTerm",  # C. elegans Life Stage (774 records)
        "WBPhenotypeTerm",  # C. elegans Phenotype (2,650 records)
        "XBATerm",  # Xenopus Anatomy (1,684 records)
        "XBEDTerm",  # Xenopus Early Development (200 records)
        "XBSTerm",  # Xenopus Stages (96 records)
        "XCOTerm",  # Experimental Conditions (1,684 records)
        "XPOTerm",  # Xenopus Phenotype (21,197 records)
        "XSMOTerm",  # Xenopus Small Molecule (444 records)
        "ZECOTerm",  # Zebrafish Experimental Conditions (161 records)
        "ZFATerm",  # Zebrafish Anatomy (3,105 records)
        "ZFSTerm",  # Zebrafish Stages (54 records)
    ]

    @classmethod
    def setUpClass(cls):
        """Initialize database connection once for all tests."""
        cls.db = DatabaseMethods()

    def test_all_ontology_types_accessible(self):
        """Test that all 45 ontology types can be searched."""

        accessible_count = 0
        empty_count = 0
        error_count = 0

        # Common search terms that likely exist across many ontologies
        search_terms = ["a", "cell", "protein", "abnormal", "0"]

        for ont_type in self.ALL_ONTOLOGY_TYPES:
            try:
                # Try multiple search terms to find at least one result
                found_result = False
                for search_term in search_terms:
                    results = self.db.search_ontology_terms(term=search_term, ontology_type=ont_type, limit=1)

                    if len(results) > 0:
                        # Validate first result
                        self.assertIsInstance(
                            results[0],
                            OntologyTermResult,
                            f"{ont_type}: Expected OntologyTermResult, got {type(results[0])}",
                        )
                        self.assertEqual(
                            results[0].ontology_type, ont_type, f"{ont_type}: Expected ontology_type to match"
                        )

                        accessible_count += 1
                        found_result = True
                        break

                if not found_result:
                    empty_count += 1

            except Exception as e:
                error_count += 1
                self.fail(f"{ont_type} failed with error: {e}")

        # All 45 should be accessible (based on our database query showing all have data)
        self.assertEqual(
            accessible_count, 45, f"Expected all 45 ontology types to be accessible, got {accessible_count}"
        )

    def test_search_with_synonyms(self):
        """Test that synonym searching works for a sample of ontology types."""
        test_cases = [
            ("WBBTTerm", "cell"),
            ("GOTerm", "nucleus"),
            ("CHEBITerm", "water"),
            ("DOTerm", "disease"),
            ("HPTerm", "abnormal"),
        ]

        for ont_type, search_term in test_cases:
            # Search with synonyms
            results_with_syn = self.db.search_ontology_terms(
                term=search_term, ontology_type=ont_type, include_synonyms=True, limit=5
            )

            # Search without synonyms
            results_without_syn = self.db.search_ontology_terms(
                term=search_term, ontology_type=ont_type, include_synonyms=False, limit=5
            )

            self.assertIsInstance(results_with_syn, list)
            self.assertIsInstance(results_without_syn, list)

            # Results should be valid
            for result in results_with_syn[:1]:
                self.assertIsInstance(result, OntologyTermResult)
                self.assertEqual(result.ontology_type, ont_type)

    def test_exact_vs_partial_match(self):
        """Test exact match vs partial match modes."""
        # Use a common term that should have exact matches
        test_cases = [
            ("GOTerm", "nucleus"),
            ("WBBTTerm", "pharynx"),
            ("CHEBITerm", "water"),
        ]

        for ont_type, search_term in test_cases:
            # Exact match
            exact_results = self.db.search_ontology_terms(
                term=search_term, ontology_type=ont_type, exact_match=True, limit=5
            )

            # Partial match
            partial_results = self.db.search_ontology_terms(
                term=search_term, ontology_type=ont_type, exact_match=False, limit=5
            )

            self.assertIsInstance(exact_results, list)
            self.assertIsInstance(partial_results, list)

            # Partial should generally have >= exact (might find more)
            # (Not always true, but usually)


if __name__ == "__main__":
    unittest.main(verbosity=2)
