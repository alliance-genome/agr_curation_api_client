"""Integration tests for literature reference search against Elasticsearch OSS 7.10.

The production literature index lives on an AWS OpenSearch Service domain
running the Elasticsearch 7.10 engine. These tests run the real opensearch-py
client against a disposable ``elasticsearch-oss:7.10.2`` server with a small
synthetic index that has the same field layout as ``references_index``.

Set ``AGR_CLIENT_TEST_LITERATURE_ES_URL`` (for example ``http://localhost:9200``)
to run them; they are skipped otherwise.
"""

import os
from typing import Iterator
from urllib.parse import urlparse

import pytest
from opensearchpy import OpenSearch

from agr_curation_api.db_methods import DatabaseConfig, DatabaseMethods, LiteratureESConfig

ES_URL = os.environ.get("AGR_CLIENT_TEST_LITERATURE_ES_URL", "")
INDEX = "references_index_client_test"

pytestmark = pytest.mark.skipif(
    not ES_URL,
    reason="Literature search integration tests require AGR_CLIENT_TEST_LITERATURE_ES_URL",
)

KEYWORD = {"type": "keyword", "normalizer": "sortNormalizer"}
INDEX_BODY = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "normalizer": {"sortNormalizer": {"type": "custom", "filter": ["lowercase", "asciifolding"]}}
        },
    },
    "mappings": {
        "properties": {
            "curie": {"type": "text", "fields": {"keyword": KEYWORD}},
            "title": {"type": "text", "fields": {"keyword": dict(KEYWORD, ignore_above=256)}},
            "citation": {"type": "text"},
            "abstract": {"type": "text"},
            "cross_references": {
                "properties": {
                    "curie": {"type": "text", "fields": {"keyword": KEYWORD}},
                    "is_obsolete": {"type": "keyword"},
                }
            },
        }
    },
}
DOCUMENTS = [
    {
        "curie": "AGRKB:101000000000001",
        "title": "Synthetic notch signalling study in fly wing discs",
        "citation": "Doe J (2020) Synthetic Journal 1:1",
        "abstract": "A synthetic test abstract.",
        "cross_references": [
            {"curie": "PMID:11111111", "is_obsolete": "false"},
            {"curie": "DOI:10.0000/synthetic.1", "is_obsolete": "false"},
        ],
    },
    {
        "curie": "AGRKB:101000000000002",
        "title": "Obsolete cross reference example",
        "citation": "Roe R (2019) Example 2:2",
        "abstract": "Another synthetic abstract.",
        "cross_references": [{"curie": "PMID:22222222", "is_obsolete": "true"}],
    },
]


@pytest.fixture(scope="module")
def literature_db() -> Iterator[DatabaseMethods]:
    admin = OpenSearch(hosts=[ES_URL])
    if admin.indices.exists(index=INDEX):
        admin.indices.delete(index=INDEX)
    admin.indices.create(index=INDEX, body=INDEX_BODY)
    for number, document in enumerate(DOCUMENTS, start=1):
        admin.index(index=INDEX, id=str(number), body=document)
    admin.indices.refresh(index=INDEX)

    parsed = urlparse(ES_URL)
    config = LiteratureESConfig()
    config.host = parsed.hostname or ""
    config.port = parsed.port or (443 if parsed.scheme == "https" else 80)
    config.index = INDEX
    config.use_ssl = parsed.scheme == "https"
    try:
        yield DatabaseMethods(config=DatabaseConfig(), literature_es_config=config)
    finally:
        admin.indices.delete(index=INDEX)


@pytest.mark.parametrize(
    "identifier, expected",
    [
        ("AGRKB:101000000000001", "AGRKB:101000000000001"),
        ("PMID:11111111", "AGRKB:101000000000001"),
        ("pmid:11111111", "AGRKB:101000000000001"),
        ("PMID:22222222", None),
        ("Synthetic notch signalling study in fly wing discs", "AGRKB:101000000000001"),
    ],
)
def test_get_literature_reference(literature_db: DatabaseMethods, identifier: str, expected: str) -> None:
    result = literature_db.get_literature_reference(identifier)
    assert (result.curie if result else None) == expected


@pytest.mark.parametrize("query", ["notch signaling wing", "Synthetc notch", "DOI:10.0000"])
def test_search_literature_references(literature_db: DatabaseMethods, query: str) -> None:
    results = literature_db.search_literature_references(query, limit=5)
    assert [result.curie for result in results] == ["AGRKB:101000000000001"]
    assert results[0].source == "literature_es"
