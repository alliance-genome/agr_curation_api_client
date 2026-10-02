"""Execute discovery and bounded hydration against disposable PostgreSQL tables.

Set AGR_CLIENT_TEST_POSTGRES_URL to a disposable PostgreSQL database. This fixture
creates only transaction-local temporary tables and rolls back every test.
"""

import os
from time import perf_counter
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from agr_curation_api.allele_candidates import search_allele_candidates


@pytest.fixture
def allele_db():
    url = os.environ.get("AGR_CLIENT_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("AGR_CLIENT_TEST_POSTGRES_URL requires a disposable PostgreSQL database")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        for ddl in (
            "CREATE TEMP TABLE biologicalentity (id bigint PRIMARY KEY, primaryexternalid text, curie text, taxon_id bigint, obsolete boolean DEFAULT false, internal boolean DEFAULT false) ON COMMIT DROP",
            "CREATE TEMP TABLE allele (id bigint PRIMARY KEY) ON COMMIT DROP",
            "CREATE TEMP TABLE gene (id bigint PRIMARY KEY) ON COMMIT DROP",
            "CREATE TEMP TABLE ontologyterm (id bigint PRIMARY KEY, curie text, name text, obsolete boolean DEFAULT false) ON COMMIT DROP",
            "CREATE TEMP TABLE slotannotation (id bigserial PRIMARY KEY, singleallele_id bigint, singlegene_id bigint, displaytext text, slotannotationtype text, obsolete boolean DEFAULT false, internal boolean DEFAULT false) ON COMMIT DROP",
            "CREATE TEMP TABLE vocabularyterm (id bigint PRIMARY KEY, name text, obsolete boolean DEFAULT false) ON COMMIT DROP",
            "CREATE TEMP TABLE slotannotation_vocabularyterm (slotannotation_id bigint, functionalimpacts_id bigint) ON COMMIT DROP",
            "CREATE TEMP TABLE slotannotation_ontologyterm (slotannotation_id bigint, mutationtypes_id bigint) ON COMMIT DROP",
            "CREATE TEMP TABLE allelegeneassociation (alleleassociationsubject_id bigint, allelegeneassociationobject_id bigint, relation_id bigint, obsolete boolean DEFAULT false, internal boolean DEFAULT false) ON COMMIT DROP",
            "CREATE INDEX ON slotannotation (singleallele_id)",
            "CREATE INDEX ON allelegeneassociation (alleleassociationsubject_id)",
            "INSERT INTO ontologyterm VALUES (1, 'NCBITaxon:10090', 'mouse', false), (2, 'NCBITaxon:7227', 'fly', false)",
            "INSERT INTO vocabularyterm VALUES (1, 'is_allele_of', false), (2, 'conditional_ready', false), (3, 'aaa_other', false)",
            "INSERT INTO biologicalentity (id, primaryexternalid, taxon_id) VALUES (1001, 'MGI:gene', 1), (1002, 'MGI:other', 1)",
            "INSERT INTO gene VALUES (1001), (1002)",
            "INSERT INTO slotannotation (singlegene_id, displaytext, slotannotationtype) VALUES (1001, 'Gene', 'GeneSymbolSlotAnnotation'), (1002, 'Other', 'GeneSymbolSlotAnnotation')",
        ):
            connection.execute(text(ddl))
        connection.execute(text("""
            INSERT INTO biologicalentity (id, primaryexternalid, taxon_id)
            SELECT i, 'MGI:' || lpad(i::text, 3, '0'), 1 FROM generate_series(1, 40) i
        """))
        connection.execute(text("INSERT INTO allele SELECT id FROM biologicalentity WHERE id <= 40"))
        connection.execute(text("""
            INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype)
            SELECT i, 'Gene allele ' || i, 'AlleleSymbolSlotAnnotation' FROM generate_series(1, 40) i
        """))
        connection.execute(text("""
            INSERT INTO allelegeneassociation (alleleassociationsubject_id, allelegeneassociationobject_id, relation_id)
            SELECT i, 1001, 1 FROM generate_series(1, 40) i
        """))
        # Record 39 was beyond the old 25-record discovery boundary.
        connection.execute(
            text(
                "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) VALUES (39, 'mutation, Cyagen', 'AlleleFullNameSlotAnnotation')"
            )
        )
        connection.execute(text("""
            WITH annotation AS (
              INSERT INTO slotannotation (singleallele_id, slotannotationtype)
              VALUES (39, 'AlleleFunctionalImpactSlotAnnotation') RETURNING id
            ) INSERT INTO slotannotation_vocabularyterm SELECT id, 2 FROM annotation
        """))
        session = SimpleNamespace(execute=connection.execute, close=lambda: None)
        yield SimpleNamespace(_create_session=lambda: session), connection
        transaction.rollback()
    engine.dispose()


def search(db, **kwargs):
    return search_allele_candidates(db, "Gene", taxon_curie="NCBITaxon:10090", limit=10, discovery_limit=25, **kwargs)


@pytest.mark.parametrize(
    "hints",
    [
        {},
        {"attribution_hint": "cyagen"},
        {"functional_impact_hint": "CONDITIONAL_READY"},
        {"attribution_hint": "Cyagen", "functional_impact_hint": "conditional_ready"},
    ],
)
def test_small_and_large_discovery_share_leading_candidates(allele_db, hints):
    db, _ = allele_db
    small = search(db, **hints)
    large = search_allele_candidates(db, "Gene", taxon_curie="NCBITaxon:10090", discovery_limit=100, limit=25, **hints)
    assert small["candidates"] == large["candidates"][:10]
    assert small["candidates"][0]["curie"] == ("MGI:039" if hints else "MGI:001")
    assert small["coverage"] == {
        "discovered_count": 25,
        "returned_count": 10,
        "discovery_limit": 25,
        "display_limit": 10,
        "discovery_capped": True,
        "display_capped": True,
        "database_total": None,
        "detail_missing_count": 0,
    }
    assert large["coverage"]["discovered_count"] == 40
    assert large["coverage"]["discovery_capped"] is False
    assert all(row["identity_status"] == "unconfirmed" for row in small["candidates"])


@pytest.mark.parametrize("exact", ["id", "name", "synonym"])
def test_exact_matches_precede_hints(allele_db, exact):
    db, conn = allele_db
    if exact == "id":
        conn.execute(text("UPDATE biologicalentity SET curie='Gene' WHERE id=1"))
    else:
        annotation_type = "AlleleFullNameSlotAnnotation" if exact == "name" else "AlleleSynonymSlotAnnotation"
        conn.execute(
            text(
                "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) VALUES (1, 'Gene', :kind)"
            ),
            {"kind": annotation_type},
        )
    result = search(db, attribution_hint="Cyagen", functional_impact_hint="conditional_ready")
    assert [row["curie"] for row in result["candidates"][:2]] == ["MGI:001", "MGI:039"]
    assert result["candidates"][0]["match_type"] == ("exact_id" if exact == "id" else "exact")


def test_hint_promotes_contains_above_prefix_and_remains_soft(allele_db):
    db, conn = allele_db
    conn.execute(
        text(
            "UPDATE slotannotation SET displaytext='unrelated Gene allele' WHERE singleallele_id=39 AND slotannotationtype='AlleleSymbolSlotAnnotation'"
        )
    )
    result = search(db, attribution_hint="Cyagen")
    assert result["candidates"][0]["curie"] == "MGI:039"
    assert result["candidates"][0]["match_type"] == "contains"
    assert len(result["candidates"]) == 10
    assert search(db, attribution_hint="absent")["candidates"][0]["curie"] == "MGI:001"


@pytest.mark.parametrize("exclusion", ["taxon", "gene", "internal", "obsolete", "impact_internal", "impact_obsolete"])
def test_scopes_and_public_annotation_filters(allele_db, exclusion):
    db, conn = allele_db
    if exclusion == "taxon":
        conn.execute(text("UPDATE biologicalentity SET taxon_id=2 WHERE id=39"))
    elif exclusion == "gene":
        conn.execute(
            text(
                "UPDATE allelegeneassociation SET allelegeneassociationobject_id=1002 WHERE alleleassociationsubject_id=39"
            )
        )
    elif exclusion in {"internal", "obsolete"}:
        conn.execute(text(f"UPDATE biologicalentity SET {exclusion}=true WHERE id=39"))
    else:
        flag = exclusion.split("_")[1]
        conn.execute(
            text(
                f"UPDATE slotannotation SET {flag}=true WHERE singleallele_id=39 AND slotannotationtype='AlleleFunctionalImpactSlotAnnotation'"
            )
        )
    result = search(db, gene_identifier="MGI:gene", functional_impact_hint="conditional_ready")
    assert result["candidates"][0]["curie"] == "MGI:001"


def test_ranking_evidence_beyond_annotation_cap(allele_db, monkeypatch):
    db, conn = allele_db
    monkeypatch.setenv("AGR_ALLELE_ANNOTATION_LIMIT", "1")
    conn.execute(
        text(
            "INSERT INTO slotannotation_vocabularyterm SELECT id, 3 FROM slotannotation WHERE singleallele_id=39 AND slotannotationtype='AlleleFunctionalImpactSlotAnnotation'"
        )
    )
    result = search(db, functional_impact_hint="conditional_ready")
    preferred = result["candidates"][0]
    assert preferred["curie"] == "MGI:039"
    assert preferred["functional_impacts"] == ["aaa_other"]
    assert preferred["annotations_capped"] == ["functional_impacts"]
    assert "structured_functional_impact" in preferred["match_reasons"]


def test_synonym_switch_and_literal_hint_characters(allele_db):
    db, conn = allele_db
    conn.execute(
        text(
            "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) VALUES (1, 'Gene', 'AlleleSynonymSlotAnnotation')"
        )
    )
    assert search(db, attribution_hint="Cyagen", include_synonyms=False)["candidates"][0]["curie"] == "MGI:039"
    assert search(db, attribution_hint="%_")["candidates"][0]["curie"] == "MGI:001"


def test_ties_and_missing_annotations_are_deterministic(allele_db):
    db, conn = allele_db
    conn.execute(
        text(
            "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) VALUES (40, 'mutation, Cyagen', 'AlleleFullNameSlotAnnotation')"
        )
    )
    result = search(db, attribution_hint="Cyagen")
    assert [row["curie"] for row in result["candidates"][:3]] == ["MGI:039", "MGI:040", "MGI:001"]
    assert result["candidates"][2]["functional_impacts"] == []


def test_broad_fixture_query_is_bounded(allele_db):
    db, conn = allele_db
    conn.execute(
        text(
            "INSERT INTO biologicalentity (id, primaryexternalid, taxon_id) SELECT i, 'MGI:' || i, 1 FROM generate_series(2000, 6999) i"
        )
    )
    conn.execute(text("INSERT INTO allele SELECT id FROM biologicalentity WHERE id >= 2000"))
    conn.execute(
        text(
            "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) SELECT i, 'Gene allele ' || i, 'AlleleSymbolSlotAnnotation' FROM generate_series(2000, 6999) i"
        )
    )
    conn.execute(text("ANALYZE slotannotation"))
    start = perf_counter()
    result = search(db, attribution_hint="Cyagen", functional_impact_hint="conditional_ready")
    elapsed = perf_counter() - start
    print(f"5040-match synthetic search: {elapsed:.3f}s, 25 hydrated, 10 returned")
    assert result["candidates"][0]["curie"] == "MGI:039"
    assert len(result["candidates"]) == 10
    assert result["coverage"]["discovered_count"] == 25


def test_attribution_uses_first_public_full_name(allele_db):
    db, conn = allele_db
    conn.execute(
        text(
            "INSERT INTO slotannotation (singleallele_id, displaytext, slotannotationtype) VALUES (1, 'first official name', 'AlleleFullNameSlotAnnotation'), (1, 'later Cyagen name', 'AlleleFullNameSlotAnnotation')"
        )
    )
    result = search(db, attribution_hint="Cyagen")
    assert result["candidates"][0]["curie"] == "MGI:039"
    other = next(row for row in result["candidates"] if row["curie"] == "MGI:001")
    assert other["name"] == "first official name"
    assert "full_name_attribution_text" not in other["match_reasons"]


def test_gene_reason_survives_capped_annotations(allele_db, monkeypatch):
    db, conn = allele_db
    monkeypatch.setenv("AGR_ALLELE_ANNOTATION_LIMIT", "1")
    conn.execute(text("UPDATE biologicalentity SET primaryexternalid='MGI:aaa' WHERE id=1002"))
    conn.execute(
        text(
            "INSERT INTO allelegeneassociation (alleleassociationsubject_id, allelegeneassociationobject_id, relation_id) VALUES (39, 1002, 1)"
        )
    )
    result = search(db, gene_identifier="MGI:gene", attribution_hint="Cyagen")
    preferred = result["candidates"][0]
    assert preferred["curie"] == "MGI:039"
    assert preferred["genes"][0]["curie"] == "MGI:aaa"
    assert "genes" in preferred["annotations_capped"]
    assert "verified_is_allele_of" in preferred["match_reasons"]
