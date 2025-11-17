#!/usr/bin/env python3
"""Test organism-agnostic convenience methods.

Tests search_anatomy_terms(), search_life_stage_terms(), and search_go_terms()
against production database.
"""

import pytest
import os
from agr_curation_api.db_methods import DatabaseMethods

pytestmark = pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)


def test_anatomy_methods():
    """Test anatomy search convenience methods."""
    db = DatabaseMethods()

    # Test C. elegans anatomy
    results = db.search_anatomy_terms("linker", "WB", limit=3)
    assert len(results) > 0, "Should find WB anatomy terms for 'linker'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test Drosophila anatomy
    results = db.search_anatomy_terms("wing", "FB", limit=3)
    assert len(results) > 0, "Should find FB anatomy terms for 'wing'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test Zebrafish anatomy
    results = db.search_anatomy_terms("somite", "ZFIN", limit=3)
    assert len(results) > 0, "Should find ZFIN anatomy terms for 'somite'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None


def test_life_stage_methods():
    """Test life stage search convenience methods."""
    db = DatabaseMethods()

    # Test C. elegans life stages
    results = db.search_life_stage_terms("L3", "WB", limit=3)
    assert len(results) > 0, "Should find WB life stage terms for 'L3'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test Drosophila life stages
    results = db.search_life_stage_terms("larval", "FB", limit=3)
    assert len(results) > 0, "Should find FB life stage terms for 'larval'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test Zebrafish life stages
    results = db.search_life_stage_terms("adult", "ZFIN", limit=3)
    assert len(results) > 0, "Should find ZFIN life stage terms for 'adult'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None


def test_go_methods():
    """Test GO term search convenience methods."""
    db = DatabaseMethods()

    # Test cellular component search
    results = db.search_go_terms("nucleus", go_aspect="cellular_component", limit=3)
    assert len(results) > 0, "Should find GO cellular component terms for 'nucleus'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test biological process search
    results = db.search_go_terms("apoptosis", go_aspect="biological_process", limit=3)
    assert len(results) > 0, "Should find GO biological process terms for 'apoptosis'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test molecular function search
    results = db.search_go_terms("kinase", go_aspect="molecular_function", limit=3)
    assert len(results) > 0, "Should find GO molecular function terms for 'kinase'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None

    # Test all GO aspects (no filtering)
    results = db.search_go_terms("cell", go_aspect=None, limit=5)
    assert len(results) > 0, "Should find GO terms for 'cell'"
    for r in results:
        assert r.curie is not None
        assert r.name is not None
        assert r.ontology_type is not None


def test_organism_switching():
    """Test organism switching with same search term."""
    db = DatabaseMethods()

    search_term = "brain"

    # C. elegans
    wb_results = db.search_anatomy_terms(search_term, "WB", limit=2)
    for r in wb_results:
        assert r.curie is not None
        assert r.name is not None

    # Drosophila
    fb_results = db.search_anatomy_terms(search_term, "FB", limit=2)
    for r in fb_results:
        assert r.curie is not None
        assert r.name is not None

    # Zebrafish
    zfin_results = db.search_anatomy_terms(search_term, "ZFIN", limit=2)
    for r in zfin_results:
        assert r.curie is not None
        assert r.name is not None

    # Mouse
    mgi_results = db.search_anatomy_terms(search_term, "MGI", limit=2)
    for r in mgi_results:
        assert r.curie is not None
        assert r.name is not None


if __name__ == "__main__":
    import sys

    try:
        test_anatomy_methods()
        test_life_stage_methods()
        test_go_methods()
        test_organism_switching()
        print("All tests passed!")
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
