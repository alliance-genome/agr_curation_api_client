"""Tests for durable allele and allele-gene association identifiers."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from agr_curation_api.db_methods import DatabaseConfig, DatabaseMethods
from agr_curation_api.exceptions import AGRAPIError


@pytest.fixture
def db_methods():
    config = Mock(spec=DatabaseConfig)
    config.connection_string = "postgresql://test:test@localhost/test"
    with patch("agr_curation_api.db_methods.create_engine"), patch("agr_curation_api.db_methods.sessionmaker"):
        yield DatabaseMethods(config)


@patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
def test_get_allele_returns_durable_database_id(mock_session_factory, db_methods):
    session = MagicMock()
    mock_session_factory.return_value = session
    session.execute.return_value.fetchone.return_value = (
        4749192,
        "WB:WBVar00000001",
        "WB:WBVar00000001",
        False,
        False,
        "NCBITaxon:6239",
        False,
        None,
        "e1",
        "<i>e1</i>",
        None,
        None,
    )

    allele = db_methods.get_allele("WB:WBVar00000001")

    assert allele is not None
    assert allele.id == 4749192
    assert allele.curie == "WB:WBVar00000001"
    assert allele.alleleSymbol is not None
    assert allele.alleleSymbol.displayText == "e1"
    sql = str(session.execute.call_args.args[0])
    assert "be.id" in sql
    assert "be.curie = :allele_id" in sql
    session.close.assert_called_once()


@patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
def test_search_allele_gene_associations_preserves_all_exact_matches(mock_session_factory, db_methods):
    session = MagicMock()
    mock_session_factory.return_value = session
    session.execute.return_value.fetchall.return_value = [
        (
            202511462,
            4749192,
            "WB:WBVar00000001",
            5277082,
            "WB:WBGene00003883",
            123,
            False,
            False,
        ),
        (
            202511999,
            4749192,
            "WB:WBVar00000001",
            5277082,
            "WB:WBGene00003883",
            456,
            False,
            False,
        ),
    ]

    results = db_methods.search_allele_gene_associations(
        " WB:WBVar00000001 ",
        " WB:WBGene00003883 ",
        limit=5,
    )

    assert [result.association_id for result in results] == [202511462, 202511999]
    assert results[0].allele_id == 4749192
    assert results[0].gene_id == 5277082
    sql = str(session.execute.call_args.args[0])
    params = session.execute.call_args.args[1]
    assert "aga.obsolete = false" in sql
    assert "allele_be.obsolete = false" in sql
    assert "gene_be.obsolete = false" in sql
    assert params == {
        "allele_identifier": "WB:WBVar00000001",
        "gene_identifier": "WB:WBGene00003883",
        "include_obsolete": False,
        "limit": 5,
    }
    session.close.assert_called_once()


def test_search_allele_gene_associations_rejects_empty_or_invalid_limits(db_methods):
    assert db_methods.search_allele_gene_associations("", "WB:WBGene00003883") == []
    assert db_methods.search_allele_gene_associations("WB:WBVar00000001", "") == []
    with pytest.raises(AGRAPIError, match="limit must be at least 1"):
        db_methods.search_allele_gene_associations(
            "WB:WBVar00000001",
            "WB:WBGene00003883",
            limit=0,
        )
