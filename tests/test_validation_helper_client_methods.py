"""Tests for validation-oriented AGRCurationAPIClient DB helper methods."""

from agr_curation_api.client import AGRCurationAPIClient


class FakeDatabaseMethods:
    def __init__(self):
        self.calls = []

    def search_ontology_terms(self, **kwargs):
        self.calls.append(("search_ontology_terms", kwargs))
        return ["ontology"]

    def search_anatomy_terms(self, **kwargs):
        self.calls.append(("search_anatomy_terms", kwargs))
        return ["anatomy"]

    def search_life_stage_terms(self, **kwargs):
        self.calls.append(("search_life_stage_terms", kwargs))
        return ["life_stage"]

    def search_go_terms(self, **kwargs):
        self.calls.append(("search_go_terms", kwargs))
        return ["go"]

    def search_disease_terms(self, **kwargs):
        self.calls.append(("search_disease_terms", kwargs))
        return ["disease"]

    def search_phenotype_terms(self, **kwargs):
        self.calls.append(("search_phenotype_terms", kwargs))
        return ["phenotype"]

    def search_chemical_terms(self, **kwargs):
        self.calls.append(("search_chemical_terms", kwargs))
        return ["chemical"]

    def search_evidence_terms(self, **kwargs):
        self.calls.append(("search_evidence_terms", kwargs))
        return ["evidence"]

    def search_taxon_terms(self, **kwargs):
        self.calls.append(("search_taxon_terms", kwargs))
        return ["taxon"]

    def search_sequence_terms(self, **kwargs):
        self.calls.append(("search_sequence_terms", kwargs))
        return ["sequence"]

    def get_reference(self, **kwargs):
        self.calls.append(("get_reference", kwargs))
        return "reference"

    def search_references(self, **kwargs):
        self.calls.append(("search_references", kwargs))
        return ["reference"]

    def get_literature_reference(self, **kwargs):
        self.calls.append(("get_literature_reference", kwargs))
        return "literature_reference"

    def search_literature_references(self, **kwargs):
        self.calls.append(("search_literature_references", kwargs))
        return ["literature_reference"]

    def get_vocabulary_term(self, **kwargs):
        self.calls.append(("get_vocabulary_term", kwargs))
        return "vocabulary_term"

    def search_vocabulary_terms(self, **kwargs):
        self.calls.append(("search_vocabulary_terms", kwargs))
        return ["vocabulary_term"]


def make_client_with_fake_db():
    client = AGRCurationAPIClient(data_source="db")
    fake_db = FakeDatabaseMethods()
    client._db_methods = fake_db
    return client, fake_db


def test_ontology_search_methods_delegate_to_database_methods():
    client, fake_db = make_client_with_fake_db()

    assert client.search_ontology_terms("cell", "GOTerm", exact_match=True, limit=3) == ["ontology"]
    assert client.search_anatomy_terms("brain", data_provider="ZFIN", limit=4) == ["anatomy"]
    assert client.search_life_stage_terms("larval", data_provider="FB", limit=5) == ["life_stage"]
    assert client.search_go_terms("nucleus", go_aspect="cellular_component", limit=6) == ["go"]
    assert client.search_disease_terms("cancer", limit=7) == ["disease"]
    assert client.search_phenotype_terms("lethal", organism="WB", limit=8) == ["phenotype"]
    assert client.search_chemical_terms("ethanol", limit=9) == ["chemical"]
    assert client.search_evidence_terms("experimental", limit=10) == ["evidence"]
    assert client.search_taxon_terms("zebrafish", limit=11) == ["taxon"]
    assert client.search_sequence_terms("exon", limit=12) == ["sequence"]

    assert fake_db.calls[0] == (
        "search_ontology_terms",
        {
            "term": "cell",
            "ontology_type": "GOTerm",
            "exact_match": True,
            "include_synonyms": True,
            "limit": 3,
        },
    )
    assert fake_db.calls[1][1]["data_provider"] == "ZFIN"
    assert fake_db.calls[3][1]["go_aspect"] == "cellular_component"


def test_reference_and_vocabulary_methods_delegate_to_database_methods():
    client, fake_db = make_client_with_fake_db()

    assert client.get_reference("PMID:31285256") == "reference"
    assert client.search_references("Zaremba", limit=2) == ["reference"]
    assert client.get_literature_reference("PMID:31285256") == "literature_reference"
    assert client.search_literature_references("NF-kB", exact_match=True, limit=1) == ["literature_reference"]
    assert client.get_vocabulary_term("Disease Relation", "is_model_of") == "vocabulary_term"
    assert client.search_vocabulary_terms(term="has_condition", vocabulary="Condition Relation Type") == [
        "vocabulary_term"
    ]

    assert fake_db.calls[0] == (
        "get_reference",
        {"identifier": "PMID:31285256", "include_obsolete": False},
    )
    assert fake_db.calls[3] == (
        "search_literature_references",
        {"query": "NF-kB", "exact_match": True, "limit": 1},
    )
    assert fake_db.calls[5][1]["vocabulary"] == "Condition Relation Type"
