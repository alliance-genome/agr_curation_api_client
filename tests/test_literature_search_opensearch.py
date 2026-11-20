"""Unit tests for the literature reference search path backed by opensearch-py.

The OpenSearch client is replaced with a stub, so no server is needed. The
stub records how the client is constructed and what request body is sent,
and returns canned hits.
"""

from typing import Any, Dict, List, Optional

import opensearchpy
import pytest

from agr_curation_api.db_methods import DatabaseConfig, DatabaseMethods, LiteratureESConfig
from agr_curation_api.exceptions import AGRAPIError


class FakeOpenSearch:
    """Stand-in for ``opensearchpy.OpenSearch`` that records calls."""

    instances: List["FakeOpenSearch"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.search_calls: List[Dict[str, Any]] = []
        self.hits: List[Dict[str, Any]] = []
        self.error: Optional[Exception] = None
        FakeOpenSearch.instances.append(self)

    def search(self, *, index: Any = None, body: Any = None) -> Dict[str, Any]:
        self.search_calls.append({"index": index, "body": body})
        if self.error is not None:
            raise self.error
        return {"hits": {"hits": [{"_source": source} for source in self.hits]}}


REFERENCE_A = {
    "curie": "AGRKB:101000000000001",
    "title": "Notch signalling in wing discs",
    "citation": "Doe J (2020) Journal 1:1",
    "cross_references": [
        {"curie": "PMID:11111111", "is_obsolete": "false"},
        {"curie": "DOI:10.0000/example.1", "is_obsolete": False},
        {"curie": "PMID:99999999", "is_obsolete": "true"},
    ],
}
REFERENCE_OBSOLETE_ONLY = {
    "curie": "AGRKB:101000000000002",
    "title": "Obsolete cross reference example",
    "citation": "Roe R (2019) Example 2:2",
    "cross_references": [{"curie": "PMID:22222222", "is_obsolete": "true"}],
}


@pytest.fixture
def fake_opensearch(monkeypatch: pytest.MonkeyPatch) -> type:
    FakeOpenSearch.instances = []
    monkeypatch.setattr(opensearchpy, "OpenSearch", FakeOpenSearch)
    return FakeOpenSearch


@pytest.fixture
def literature_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_HOST", "literature.example.org")
    monkeypatch.setenv("ELASTICSEARCH_PORT", "443")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "references_index")
    monkeypatch.delenv("ELASTICSEARCH_SCHEME", raising=False)


def _db_methods() -> DatabaseMethods:
    return DatabaseMethods(config=DatabaseConfig(), literature_es_config=LiteratureESConfig())


def _should_clauses(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    return body["query"]["bool"]["should"]


def test_client_is_built_from_environment_once(fake_opensearch: type, literature_env: None) -> None:
    db = _db_methods()
    first = db._get_literature_es_client()
    second = db._get_literature_es_client()

    assert first is second
    assert len(fake_opensearch.instances) == 1
    assert first.init_kwargs == {
        "hosts": ["https://literature.example.org:443"],
        "timeout": 30,
        "max_retries": 3,
        "retry_on_timeout": True,
    }


def test_http_scheme_override(fake_opensearch: type, literature_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELASTICSEARCH_PORT", "9200")
    monkeypatch.setenv("ELASTICSEARCH_SCHEME", "http")
    client = _db_methods()._get_literature_es_client()
    assert client.init_kwargs["hosts"] == ["http://literature.example.org:9200"]


def test_missing_host_raises_without_building_client(
    fake_opensearch: type, literature_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ELASTICSEARCH_HOST", "")
    with pytest.raises(AGRAPIError, match="ELASTICSEARCH_HOST"):
        _db_methods().search_literature_references("notch")
    assert fake_opensearch.instances == []


def test_empty_query_returns_no_results_without_client(fake_opensearch: type, literature_env: None) -> None:
    assert _db_methods().search_literature_references("   ") == []
    assert fake_opensearch.instances == []


def test_free_text_search_sends_fuzzy_body_and_parses_hits(fake_opensearch: type, literature_env: None) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.hits = [REFERENCE_A]

    results = db.search_literature_references("notch signaling wing", limit=5)

    assert len(client.search_calls) == 1
    call = client.search_calls[0]
    assert call["index"] == "references_index"
    body = call["body"]
    assert body["size"] == 5
    assert body["_source"] == ["curie", "title", "citation", "cross_references"]
    assert body["query"]["bool"]["minimum_should_match"] == 1
    clause_types = [next(iter(clause)) for clause in _should_clauses(body)]
    assert clause_types == ["multi_match", "multi_match", "match_phrase", "wildcard", "wildcard"]
    assert _should_clauses(body)[1]["multi_match"]["fuzziness"] == "AUTO"

    assert len(results) == 1
    result = results[0]
    assert result.reference_id is None
    assert result.curie == "AGRKB:101000000000001"
    assert result.title == "Notch signalling in wing discs"
    assert result.short_citation == "Doe J (2020) Journal 1:1"
    assert result.cross_references == ["PMID:11111111", "DOI:10.0000/example.1"]
    assert result.source == "literature_es"


def test_xref_search_over_fetches_and_drops_obsolete_only_matches(
    fake_opensearch: type, literature_env: None
) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.hits = [REFERENCE_OBSOLETE_ONLY, REFERENCE_A]

    results = db.search_literature_references("PMID:", limit=2)

    body = client.search_calls[0]["body"]
    assert body["size"] == 20
    assert _should_clauses(body) == [
        {"term": {"cross_references.curie.keyword": {"value": "PMID:", "boost": 5.0}}},
        {"wildcard": {"cross_references.curie.keyword": {"value": "*pmid:*", "boost": 1.0}}},
    ]
    assert [result.curie for result in results] == ["AGRKB:101000000000001"]


def test_get_literature_reference_uses_exact_match_and_returns_first_hit(
    fake_opensearch: type, literature_env: None
) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.hits = [REFERENCE_A]

    result = db.get_literature_reference("PMID:11111111")

    body = client.search_calls[0]["body"]
    assert body["size"] == 20
    assert _should_clauses(body) == [
        {"term": {"curie.keyword": {"value": "PMID:11111111", "boost": 5.0}}},
        {"term": {"cross_references.curie.keyword": {"value": "PMID:11111111", "boost": 4.0}}},
        {"term": {"title.keyword": {"value": "PMID:11111111", "boost": 2.0}}},
        {"match_phrase": {"title": {"query": "PMID:11111111", "boost": 1.0}}},
    ]
    assert result is not None
    assert result.curie == "AGRKB:101000000000001"


def test_get_literature_reference_obsolete_only_xref_returns_none(
    fake_opensearch: type, literature_env: None
) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.hits = [REFERENCE_OBSOLETE_ONLY]

    assert db.get_literature_reference("PMID:22222222") is None


def test_get_literature_reference_by_agrkb_curie(fake_opensearch: type, literature_env: None) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.hits = [REFERENCE_A]

    result = db.get_literature_reference("AGRKB:101000000000001")

    assert client.search_calls[0]["body"]["size"] == 1
    assert result is not None
    assert result.curie == "AGRKB:101000000000001"


def test_search_errors_are_wrapped(fake_opensearch: type, literature_env: None) -> None:
    db = _db_methods()
    client = db._get_literature_es_client()
    client.error = opensearchpy.ConnectionError("N/A", "connection refused", Exception("refused"))

    with pytest.raises(AGRAPIError, match="literature references"):
        db.search_literature_references("notch")
