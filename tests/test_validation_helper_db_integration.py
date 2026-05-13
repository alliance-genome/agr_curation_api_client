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


def scalar_or_none(db: DatabaseMethods, query: str):
    session = db._create_session()
    try:
        return session.execute(text(query)).scalar()
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

    obsolete_reference_curie = scalar_or_none(
        db,
        """
        SELECT ice.curie
        FROM informationcontententity ice
        JOIN reference r ON r.id = ice.id
        WHERE ice.obsolete = true
        LIMIT 1
        """,
    )
    if obsolete_reference_curie:
        assert db.get_reference(obsolete_reference_curie) is None


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

    obsolete_only_xref = scalar_or_none(
        db,
        """
        SELECT cr.curie
        FROM cross_reference cr
        WHERE cr.is_obsolete = true
          AND cr.curie IS NOT NULL
          AND NOT EXISTS (
              SELECT 1
              FROM cross_reference current_cr
              WHERE current_cr.curie = cr.curie
                AND current_cr.is_obsolete = false
          )
        LIMIT 1
        """,
    )
    if obsolete_only_xref:
        assert db.get_literature_reference(obsolete_only_xref) is None
