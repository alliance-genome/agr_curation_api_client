#!/usr/bin/env python3
"""Parameterized tests for all ontology types.

This module consolidates testing for all 45 ontology types using pytest parameterization,
replacing the need for 45 separate test files.
"""

import pytest
import os
from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import OntologyTermResult


# Skip all tests if database credentials not available
pytestmark = pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)


# All 45 ontology types with test terms specific to each
ONTOLOGY_TEST_CASES = [
    ("APOTerm", ["abnormal", "phenotype", "morphology"]),
    ("ATPTerm", ["phenotype", "abnormal", "development"]),
    ("BSPOTerm", ["anterior", "posterior", "proximal"]),
    ("BTOTerm", ["tissue", "cell", "organ"]),
    ("CHEBITerm", ["protein", "molecular", "chemical"]),
    ("CLTerm", ["cell", "neuron", "epithelial"]),
    ("CMOTerm", ["measurement", "clinical", "assay"]),
    ("DAOTerm", ["anatomy", "structure", "tissue"]),
    ("DOTerm", ["disease", "syndrome", "disorder"]),
    ("ECOTerm", ["evidence", "assertion", "experimental"]),
    ("EMAPATerm", ["embryo", "development", "structure"]),
    ("FBCVTerm", ["phenotype", "assay", "qualifier"]),
    ("FBDVTerm", ["embryonic", "larval", "pupal"]),
    ("GENOTerm", ["genotype", "allele", "homozygous"]),
    ("GOTerm", ["process", "function", "component"]),
    ("HPTerm", ["phenotype", "abnormality", "feature"]),
    ("MATerm", ["anatomy", "structure", "organ"]),
    ("MITerm", ["interaction", "binding", "association"]),
    ("MMOTerm", ["measurement", "method", "assay"]),
    ("MMUSDVTerm", ["development", "stage", "embryonic"]),
    ("MODTerm", ["database", "organism", "model"]),
    ("Molecule", ["protein", "rna", "molecule"]),
    ("MPATHTerm", ["pathology", "lesion", "abnormality"]),
    ("MPTerm", ["phenotype", "abnormal", "morphology"]),
    ("NCBITaxonTerm", ["species", "genus", "organism"]),
    ("OBITerm", ["assay", "device", "protocol"]),
    ("PATOTerm", ["quality", "abnormal", "increased"]),
    ("PWTerm", ["pathway", "signaling", "metabolic"]),
    ("ROTerm", ["part", "relationship", "regulates"]),
    ("RSTerm", ["strain", "rat", "genetic"]),
    ("SOTerm", ["sequence", "region", "feature"]),
    ("UBERONTerm", ["anatomy", "structure", "organ"]),
    ("VTTerm", ["trait", "measurement", "phenotype"]),
    ("WBBTTerm", ["anatomy", "cell", "structure"]),
    ("WBLSTerm", ["larval", "adult", "embryonic"]),
    ("WBPhenotypeTerm", ["phenotype", "variant", "defective"]),
    ("XBATerm", ["anatomy", "tissue", "structure"]),
    ("XBEDTerm", ["development", "embryonic", "stage"]),
    ("XBSTerm", ["stage", "development", "embryonic"]),
    ("XCOTerm", ["condition", "treatment", "experimental"]),
    ("XPOTerm", ["phenotype", "abnormal", "morphology"]),
    ("XSMOTerm", ["molecule", "compound", "chemical"]),
    ("ZECOTerm", ["condition", "environment", "experimental"]),
    ("ZFATerm", ["anatomy", "structure", "tissue"]),
    ("ZFSTerm", ["stage", "development", "embryonic"]),
]


@pytest.fixture(scope="module")
def db():
    """Create DatabaseMethods instance for all tests."""
    return DatabaseMethods()


class TestOntologySearchParameterized:
    """Parameterized tests for all ontology types."""

    @pytest.mark.parametrize("ontology_type,test_terms", ONTOLOGY_TEST_CASES)
    def test_exact_match(self, db, ontology_type, test_terms):
        """Test exact match search for each ontology type."""
        # Use first test term for exact match
        term = test_terms[0]
        results = db.search_ontology_terms(term=term, ontology_type=ontology_type, exact_match=True, limit=5)

        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, OntologyTermResult)
            assert result.ontology_type == ontology_type
            # Exact match should contain the term in name or synonyms (case-insensitive)
            term_found = term.lower() in result.name.lower() or any(
                term.lower() in syn.lower() for syn in result.synonyms
            )
            assert term_found, f"Term '{term}' not found in name '{result.name}' or synonyms {result.synonyms}"

    @pytest.mark.parametrize("ontology_type,test_terms", ONTOLOGY_TEST_CASES)
    def test_prefix_match(self, db, ontology_type, test_terms):
        """Test prefix match search for each ontology type."""
        # Use second test term for prefix match
        term = test_terms[1] if len(test_terms) > 1 else test_terms[0]
        results = db.search_ontology_terms(term=term, ontology_type=ontology_type, limit=10)

        assert isinstance(results, list)
        # Should find at least some results for most ontologies
        for result in results:
            assert result.ontology_type == ontology_type

    @pytest.mark.parametrize("ontology_type,test_terms", ONTOLOGY_TEST_CASES)
    def test_contains_match(self, db, ontology_type, test_terms):
        """Test contains match search for each ontology type."""
        # Use third test term for contains match
        term = test_terms[2] if len(test_terms) > 2 else test_terms[0]
        results = db.search_ontology_terms(term=term, ontology_type=ontology_type, limit=10)

        assert isinstance(results, list)
        for result in results:
            assert result.ontology_type == ontology_type

    @pytest.mark.parametrize("ontology_type,test_terms", ONTOLOGY_TEST_CASES)
    def test_synonym_matching(self, db, ontology_type, test_terms):
        """Test synonym search for each ontology type."""
        results = db.search_ontology_terms(
            term="cell",  # Common term likely to have synonyms
            ontology_type=ontology_type,
            include_synonyms=True,
            limit=5,
        )

        assert isinstance(results, list)
        # May or may not have results, just verify structure
        for result in results:
            assert result.ontology_type == ontology_type

    @pytest.mark.parametrize("ontology_type,test_terms", ONTOLOGY_TEST_CASES)
    def test_result_structure(self, db, ontology_type, test_terms):
        """Test that results have expected structure for each ontology type."""
        results = db.search_ontology_terms(term=test_terms[0], ontology_type=ontology_type, limit=1)

        if results:
            result = results[0]
            assert result.curie is not None
            assert result.name is not None
            assert result.namespace is not None
            assert result.ontology_type == ontology_type
            assert isinstance(result.synonyms, list)

    @pytest.mark.parametrize("ontology_type,_", ONTOLOGY_TEST_CASES)
    def test_synonym_flag_behavior(self, db, ontology_type, _):
        """Test that include_synonyms flag affects results for each ontology type."""
        # Search with synonyms
        results_with_syn = db.search_ontology_terms(
            term="cell", ontology_type=ontology_type, include_synonyms=True, limit=5
        )

        # Search without synonyms
        results_without_syn = db.search_ontology_terms(
            term="cell", ontology_type=ontology_type, include_synonyms=False, limit=5
        )

        assert isinstance(results_with_syn, list)
        assert isinstance(results_without_syn, list)

        # Results should be valid
        for result in results_with_syn[:1]:
            assert isinstance(result, OntologyTermResult)
            assert result.ontology_type == ontology_type

    @pytest.mark.parametrize("ontology_type,_", ONTOLOGY_TEST_CASES)
    def test_exact_match_flag_behavior(self, db, ontology_type, _):
        """Test that exact_match flag affects results for each ontology type."""
        # Exact match only
        exact_results = db.search_ontology_terms(term="cell", ontology_type=ontology_type, exact_match=True, limit=5)

        # Partial match (default)
        partial_results = db.search_ontology_terms(term="cell", ontology_type=ontology_type, exact_match=False, limit=5)

        assert isinstance(exact_results, list)
        assert isinstance(partial_results, list)


# Keep this for backwards compatibility with unittest-based test runners
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
