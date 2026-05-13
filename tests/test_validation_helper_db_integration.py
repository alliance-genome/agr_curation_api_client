"""Integration tests for validation-oriented database helper methods."""

import os

import pytest
from sqlalchemy import text

from agr_curation_api.db_methods import DatabaseMethods

pytestmark = pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)


def current_database(db: DatabaseMethods) -> str:
    session = db._create_session()
    try:
        return session.execute(text("select current_database()")).scalar_one()
    finally:
        session.close()


def test_curation_validation_helpers_against_live_curation_db():
    db = DatabaseMethods()
    if current_database(db) != "curation":
        pytest.skip("Requires a curation database connection")

    phenotype_results = db.search_phenotype_terms("lethal", organism="WB", limit=2)
    assert phenotype_results
    assert all(result.ontology_type == "WBPhenotypeTerm" for result in phenotype_results)

    vocabulary_term = db.get_vocabulary_term("Disease Relation", "is_model_of")
    assert vocabulary_term is not None
    assert vocabulary_term.vocabulary == "Disease Relation"
    assert vocabulary_term.name == "is_model_of"
    assert vocabulary_term.obsolete is False

    reference_results = db.search_references("PMID:", limit=3)
    assert reference_results
    pmid = next(
        cross_ref
        for result in reference_results
        for cross_ref in result.cross_references
        if cross_ref.startswith("PMID:")
    )
    exact_reference = db.get_reference(pmid)
    assert exact_reference is not None
    assert exact_reference.curie
    assert pmid in exact_reference.cross_references


def test_literature_reference_helpers_against_live_literature_db():
    db = DatabaseMethods()
    if current_database(db) != "literature":
        pytest.skip("Requires a literature database connection")

    reference_results = db.search_literature_references("PMID:", limit=3)
    assert reference_results
    pmid = next(
        cross_ref
        for result in reference_results
        for cross_ref in result.cross_references
        if cross_ref.startswith("PMID:")
    )
    exact_reference = db.get_literature_reference(pmid)
    assert exact_reference is not None
    assert exact_reference.curie
    assert exact_reference.title
    assert pmid in exact_reference.cross_references
