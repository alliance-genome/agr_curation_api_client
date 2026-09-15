"""Bounded allele retrieval contracts; no live DB needed."""

from unittest.mock import MagicMock

import pytest

from agr_curation_api.allele_candidates import search_allele_candidates, get_allele_candidate_details


def fixture_db(count=31, ranks=None):
    session = MagicMock()
    db = MagicMock()
    db._create_session.return_value = session
    rows = [
        {
            "database_id": i,
            "curie": f"MGI:{i}",
            "literal_rank": (ranks or {}).get(i, 2),
            "matched_text": f"Gene allele {i}",
        }
        for i in range(count)
    ]
    details = [
        {
            "database_id": row["database_id"],
            "curie": row["curie"],
            "taxon": "NCBITaxon:10090",
            "symbol": row["matched_text"],
            "name": "mutation, Test Source" if i in (29, 30) else None,
            "synonyms": ["flox"] if i == 29 else [],
            "genes": [{"curie": "MGI:gene", "symbol": "Gene", "relation": "is_allele_of"}],
            "functional_impacts": ["conditional_ready"] if i == 29 else [],
            "mutation_types": [],
        }
        for i, row in enumerate(rows)
    ]
    responses = [MagicMock(), MagicMock(), MagicMock()]
    responses[1].mappings.return_value.all.return_value = rows
    responses[2].mappings.return_value.all.return_value = details
    session.execute.side_effect = responses
    return db, session, responses, details


def test_rank_beyond_display_cap_with_separate_soft_clues():
    db, session, _, _ = fixture_db()
    result = search_allele_candidates(
        db,
        "Gene",
        gene_identifier="MGI:gene",
        attribution_hint="Test Source",
        functional_impact_hint="conditional_ready",
        limit=20,
    )
    assert result["candidates"][0]["curie"] == "MGI:29"
    assert "MGI:30" in [c["curie"] for c in result["candidates"]]
    assert result["coverage"]["discovered_count"] == 31
    assert result["coverage"]["display_capped"] is True
    assert result["coverage"]["discovery_capped"] is False
    assert all(c["identity_status"] == "unconfirmed" for c in result["candidates"])
    session.close.assert_called_once()


def test_discovery_uses_extra_record_not_false_total():
    db, _, responses, details = fixture_db(4)
    responses[2].mappings.return_value.all.return_value = details[:3]
    result = search_allele_candidates(db, "Gene", discovery_limit=3, limit=2)
    assert result["coverage"]["discovery_capped"] is True
    assert result["coverage"]["discovered_count"] == 3
    assert result["coverage"]["database_total"] is None


def test_exact_identifier_stays_ahead_of_soft_clues_and_missing_impacts_not_excluded():
    db, _, _, _ = fixture_db(ranks={0: 0})
    result = search_allele_candidates(
        db, "MGI:0", attribution_hint="Test Source", functional_impact_hint="conditional_ready", limit=40
    )
    assert result["candidates"][0]["curie"] == "MGI:0"
    assert len(result["candidates"]) == 31
    assert result["candidates"][0]["functional_impacts"] == []


def test_parameterized_scoped_sql_and_literal_wildcards():
    db, session, _, _ = fixture_db()
    search_allele_candidates(db, "a_%'", taxon_curie="NCBITaxon:10090", gene_identifier="MGI:gene")
    sql, params = session.execute.call_args_list[1].args
    assert "a_%'" not in str(sql)
    assert params["contains"] == "%a\\_\\%'%"
    assert params["taxon"] == "NCBITaxon:10090"
    assert "NOT aga.obsolete" in str(sql) and "NOT aga.internal" in str(sql)
    assert "gb.taxon_id=ab.taxon_id" in str(sql) and "rel.name='is_allele_of'" in str(sql)
    assert ":gene IS NULL OR be.id IN" in str(sql)
    assert "upper(sa.displaytext) LIKE" in str(sql)
    assert "selected_gene_ids AS MATERIALIZED" in str(sql)
    assert "gene_scope scope JOIN LATERAL" in str(sql)


def test_outage_is_not_no_match_and_session_closes():
    db, session, _, _ = fixture_db()
    session.execute.side_effect = TimeoutError("fixture timeout")
    with pytest.raises(TimeoutError):
        search_allele_candidates(db, "Gene")
    session.close.assert_called_once()


def test_empty_results_and_limits(monkeypatch):
    db, session, _, _ = fixture_db(0)
    assert search_allele_candidates(db, "no match")["candidates"] == []
    assert session.execute.call_count == 2
    with pytest.raises(ValueError):
        search_allele_candidates(db, "Gene", discovery_limit=1001)
    with pytest.raises(ValueError):
        search_allele_candidates(db, "")
    monkeypatch.setenv("AGR_ALLELE_DISCOVERY_MAX", "1")
    with pytest.raises(ValueError):
        get_allele_candidate_details(db, ["MGI:1", "MGI:2"])


def test_detail_annotations_are_bounded_and_reported(monkeypatch):
    db, session, responses, details = fixture_db(1)
    details[0]["synonyms"] = ["a", "b", "c"]
    monkeypatch.setenv("AGR_ALLELE_ANNOTATION_LIMIT", "2")
    responses[1].mappings.return_value.all.return_value = details
    session.execute.side_effect = responses[:2]
    result = get_allele_candidate_details(db, ["MGI:0"])
    assert result[0]["synonyms"] == ["a", "b"]
    assert result[0]["annotations_capped"] == ["synonyms"]


def test_discovery_details_join_by_stable_id_not_overlapping_text_identifiers():
    db, session, _, details = fixture_db(2)
    # The same displayed identifier can originate in different identifier columns.
    # Separate database rows must retain their own rank and never fetch a third row
    # through the public detail endpoint's primaryexternalid OR curie predicate.
    details[1]["curie"] = details[0]["curie"]
    result = search_allele_candidates(db, "Gene")
    sql, params = session.execute.call_args_list[2].args
    assert "be.id = ANY(:identifiers)" in str(sql)
    assert "be.curie = ANY(:identifiers)" not in str(sql)
    assert params["identifiers"] == [0, 1]
    assert len(result["candidates"]) == 2
    assert result["coverage"]["detail_missing_count"] == 0
    assert all("database_id" not in row for row in result["candidates"])


def test_curie_only_and_unidentified_records_do_not_collapse_discovery_keys():
    db, session, _, details = fixture_db(3)
    details[0]["curie"] = "curie-only-allele"
    details[1]["curie"] = None
    result = search_allele_candidates(db, "Gene")
    assert len(result["candidates"]) == 3
    assert result["coverage"]["detail_missing_count"] == 0
    sql, params = session.execute.call_args_list[2].args
    assert "COALESCE(NULLIF(be.primaryexternalid, ''), NULLIF(be.curie, '')) AS curie" in str(sql)
    assert params["identifiers"] == [0, 1, 2]


def test_public_detail_lookup_accepts_both_identifier_columns():
    db, session, responses, details = fixture_db(1)
    responses[1].mappings.return_value.all.return_value = details
    session.execute.side_effect = responses[:2]
    result = get_allele_candidate_details(db, ["alternate-curie"])
    sql, params = session.execute.call_args_list[1].args
    assert "be.primaryexternalid = ANY(:identifiers) OR be.curie = ANY(:identifiers)" in str(sql)
    assert params["identifiers"] == ["alternate-curie"]
    assert "database_id" not in result[0]


def test_null_impact_names_are_missing_information_not_a_ranking_crash():
    db, session, _, details = fixture_db(1)
    details[0]["functional_impacts"] = [None, "conditional_ready"]
    result = search_allele_candidates(db, "Gene", functional_impact_hint="conditional_ready")
    assert result["candidates"][0]["functional_impacts"] == ["conditional_ready"]
    assert "structured_functional_impact" in result["candidates"][0]["match_reasons"]
    assert "vt.name IS NOT NULL" in str(session.execute.call_args_list[2].args[0])
