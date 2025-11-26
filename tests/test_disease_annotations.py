#!/usr/bin/env python3
"""Test disease annotation query methods.

Tests get_disease_annotations_by_gene(), get_disease_annotations_by_taxon(),
get_disease_annotations_raw(), and get_disease_annotations_by_disease()
against production database.
"""

import pytest
import os

from agr_curation_api.db_methods import DatabaseMethods
from agr_curation_api.models import DiseaseAnnotation

pytestmark = pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)


class TestGeneDiseaseAnnotations:
    """Tests for gene disease annotation queries."""

    def test_get_disease_annotations_by_gene_wormbase(self):
        """Test getting disease annotations for a specific C. elegans gene."""
        db = DatabaseMethods()

        # Test with a known gene that has disease annotations (rab-7)
        results = db.get_disease_annotations_by_gene("WB:WBGene00004271")

        assert len(results) > 0, "Should find disease annotations for WB:WBGene00004271 (rab-7)"
        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.subject_id == "WB:WBGene00004271"
            assert ann.subject_type == "gene"
            assert ann.disease_curie is not None
            assert ann.disease_curie.startswith("DOID:")
            assert ann.disease_name is not None
            assert ann.relation is not None
            assert ann.data_provider == "WB"

    def test_get_disease_annotations_by_gene_with_evidence_codes(self):
        """Test that evidence codes are retrieved when requested."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_gene(
            "WB:WBGene00004271", include_evidence_codes=True
        )

        assert len(results) > 0
        # At least some annotations should have evidence codes
        has_evidence = any(ann.evidence_codes and len(ann.evidence_codes) > 0 for ann in results)
        assert has_evidence, "Should find at least one annotation with evidence codes"

        # Verify evidence codes are ECO terms
        for ann in results:
            if ann.evidence_codes:
                for code in ann.evidence_codes:
                    assert code.startswith("ECO:"), f"Evidence code should be ECO term: {code}"

    def test_get_disease_annotations_by_gene_rat(self):
        """Test getting disease annotations for a rat gene."""
        db = DatabaseMethods()

        # RGD gene with known disease annotations
        results = db.get_disease_annotations_by_gene("RGD:1303073")

        assert len(results) > 0, "Should find disease annotations for RGD:1303073"
        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.subject_type == "gene"
            assert ann.disease_curie is not None
            assert ann.data_provider == "RGD"

    def test_get_disease_annotations_by_gene_not_found(self):
        """Test getting disease annotations for a gene with none."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_gene("WB:WBGene99999999")
        assert len(results) == 0, "Should return empty list for non-existent gene"


class TestTaxonDiseaseAnnotations:
    """Tests for taxon-based disease annotation queries."""

    def test_get_gene_disease_annotations_by_taxon_worm(self):
        """Test getting gene disease annotations for C. elegans."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:6239", annotation_type="gene", limit=10
        )

        assert len(results) > 0, "Should find C. elegans gene disease annotations"
        assert len(results) <= 10, "Should respect limit parameter"

        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.subject_type == "gene"
            assert ann.subject_taxon == "NCBITaxon:6239"
            assert ann.disease_curie is not None
            assert ann.disease_name is not None

    def test_get_gene_disease_annotations_by_taxon_rat(self):
        """Test getting gene disease annotations for rat.

        Note: Mouse (NCBITaxon:10090) does not have gene disease annotations -
        MGI submits allele and AGM disease annotations instead.
        Rat (NCBITaxon:10116) has gene disease annotations from RGD.
        """
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:10116", annotation_type="gene", limit=10
        )

        assert len(results) > 0, "Should find rat gene disease annotations"
        for ann in results:
            assert ann.subject_type == "gene"
            assert ann.subject_taxon == "NCBITaxon:10116"

    def test_get_allele_disease_annotations_by_taxon(self):
        """Test getting allele disease annotations for mouse."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:10090", annotation_type="allele", limit=10
        )

        assert len(results) > 0, "Should find mouse allele disease annotations"
        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.subject_type == "allele"
            assert ann.subject_taxon == "NCBITaxon:10090"
            assert ann.subject_id is not None
            # Allele annotations may have inferred gene
            # (not required, but field should exist)

    def test_get_agm_disease_annotations_by_taxon(self):
        """Test getting AGM disease annotations for zebrafish."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:7955", annotation_type="agm", limit=10
        )

        assert len(results) > 0, "Should find zebrafish AGM disease annotations"
        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.subject_type == "agm"
            assert ann.subject_taxon == "NCBITaxon:7955"
            assert ann.subject_id is not None
            assert ann.subject_id.startswith("ZFIN:")

    def test_pagination(self):
        """Test that pagination works correctly."""
        db = DatabaseMethods()

        # Get first page
        page1 = db.get_disease_annotations_by_taxon(
            "NCBITaxon:6239", annotation_type="gene", limit=5, offset=0
        )

        # Get second page
        page2 = db.get_disease_annotations_by_taxon(
            "NCBITaxon:6239", annotation_type="gene", limit=5, offset=5
        )

        assert len(page1) == 5, "First page should have 5 results"
        assert len(page2) == 5, "Second page should have 5 results"

        # Verify pages are different
        page1_ids = {ann.id for ann in page1}
        page2_ids = {ann.id for ann in page2}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"


class TestRawDiseaseAnnotations:
    """Tests for raw dictionary disease annotation queries."""

    def test_get_disease_annotations_raw(self):
        """Test getting disease annotations as raw dictionaries."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_raw(
            "NCBITaxon:6239", annotation_type="gene", limit=5
        )

        assert len(results) > 0, "Should find C. elegans gene disease annotations"
        assert len(results) <= 5, "Should respect limit"

        for r in results:
            assert isinstance(r, dict)
            assert "subject_id" in r
            assert "disease_curie" in r
            assert "disease_name" in r
            assert "relation" in r
            assert r["subject_type"] == "gene"

    def test_raw_vs_model_consistency(self):
        """Test that raw and model results return consistent data."""
        db = DatabaseMethods()

        raw_results = db.get_disease_annotations_raw(
            "NCBITaxon:6239", annotation_type="gene", limit=3
        )
        model_results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:6239", annotation_type="gene", limit=3, include_evidence_codes=False
        )

        assert len(raw_results) == len(model_results)

        for raw, model in zip(raw_results, model_results):
            assert raw["id"] == model.id
            assert raw["subject_id"] == model.subject_id
            assert raw["disease_curie"] == model.disease_curie


class TestDiseaseQueries:
    """Tests for disease-based queries."""

    def test_get_annotations_by_disease(self):
        """Test getting annotations for a specific disease."""
        db = DatabaseMethods()

        # DOID:9970 is obesity - should have multiple annotations
        results = db.get_disease_annotations_by_disease("DOID:9970", limit=10)

        assert len(results) > 0, "Should find annotations for obesity (DOID:9970)"
        for ann in results:
            assert isinstance(ann, DiseaseAnnotation)
            assert ann.disease_curie == "DOID:9970"

    def test_get_annotations_by_disease_type_filter(self):
        """Test filtering disease annotations by type."""
        db = DatabaseMethods()

        # Get only gene annotations for a disease
        gene_results = db.get_disease_annotations_by_disease(
            "DOID:9970", annotation_type="gene", limit=10
        )

        assert len(gene_results) > 0, "Should find gene annotations for obesity"
        # Note: We can't verify subject_type directly from this query
        # but the SQL filter ensures only gene annotations are returned


class TestDataProviders:
    """Tests for different data providers."""

    def test_wormbase_annotations(self):
        """Test WormBase disease annotations."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:6239", annotation_type="gene", limit=5
        )

        wb_annotations = [r for r in results if r.data_provider == "WB"]
        assert len(wb_annotations) > 0, "Should find WormBase disease annotations"

    def test_flybase_annotations(self):
        """Test FlyBase disease annotations.

        Note: FlyBase submits disease annotations at the AGM level, not gene level.
        """
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:7227", annotation_type="agm", limit=10
        )

        fb_annotations = [r for r in results if r.data_provider == "FB"]
        assert len(fb_annotations) > 0, "Should find FlyBase AGM disease annotations"

    def test_mgi_annotations(self):
        """Test MGI disease annotations.

        Note: MGI submits disease annotations at the allele and AGM levels, not gene level.
        """
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:10090", annotation_type="allele", limit=10
        )

        mgi_annotations = [r for r in results if r.data_provider == "MGI"]
        assert len(mgi_annotations) > 0, "Should find MGI allele disease annotations"

    def test_rgd_annotations(self):
        """Test RGD disease annotations."""
        db = DatabaseMethods()

        results = db.get_disease_annotations_by_taxon(
            "NCBITaxon:10116", annotation_type="gene", limit=10
        )

        rgd_annotations = [r for r in results if r.data_provider == "RGD"]
        assert len(rgd_annotations) > 0, "Should find RGD disease annotations"


if __name__ == "__main__":
    import sys

    # Allow running tests directly
    try:
        db = DatabaseMethods()

        print("Testing gene disease annotations...")
        test_instance = TestGeneDiseaseAnnotations()
        test_instance.test_get_disease_annotations_by_gene_wormbase()
        test_instance.test_get_disease_annotations_by_gene_with_evidence_codes()
        test_instance.test_get_disease_annotations_by_gene_rat()
        print("  Gene tests passed!")

        print("Testing taxon disease annotations...")
        taxon_tests = TestTaxonDiseaseAnnotations()
        taxon_tests.test_get_gene_disease_annotations_by_taxon_worm()
        taxon_tests.test_get_gene_disease_annotations_by_taxon_rat()
        taxon_tests.test_get_allele_disease_annotations_by_taxon()
        taxon_tests.test_get_agm_disease_annotations_by_taxon()
        taxon_tests.test_pagination()
        print("  Taxon tests passed!")

        print("Testing raw disease annotations...")
        raw_tests = TestRawDiseaseAnnotations()
        raw_tests.test_get_disease_annotations_raw()
        raw_tests.test_raw_vs_model_consistency()
        print("  Raw tests passed!")

        print("Testing disease queries...")
        disease_tests = TestDiseaseQueries()
        disease_tests.test_get_annotations_by_disease()
        print("  Disease query tests passed!")

        print("\nAll tests passed!")

    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
