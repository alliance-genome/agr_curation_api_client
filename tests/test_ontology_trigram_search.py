#!/usr/bin/env python
"""Unit tests for the Tier 4 (pg_trgm) trigram fuzzy match in search_ontology_terms.

These tests mock the SQLAlchemy session so they run without a live database, in the
same style as tests/test_fuzzy_search.py. They verify:
  - Tier 4 runs only when the exact/prefix/contains tiers under-fill the limit.
  - Tier 4 is skipped when earlier tiers already satisfy the limit.
  - Trigram rows are mapped to OntologyTermResult with match_score / matched_field /
    match_type='trigram' populated, and matched_field follows the higher field score.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

from agr_curation_api.db_methods import DatabaseMethods, DatabaseConfig
from agr_curation_api.models import OntologyTermResult


class TestOntologyTrigramTier(unittest.TestCase):
    """Test suite for the trigram (Tier 4) fuzzy match path."""

    def setUp(self):
        """Create a DatabaseMethods instance with engine/sessionmaker mocked out."""
        self.mock_config = Mock(spec=DatabaseConfig)
        self.mock_config.connection_string = "postgresql://test:test@localhost/test"
        with patch("agr_curation_api.db_methods.create_engine"), patch(
            "agr_curation_api.db_methods.sessionmaker"
        ):
            self.db = DatabaseMethods(self.mock_config)

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_tier_runs_when_earlier_tiers_underfill(self, mock_session_factory):
        """When exact/prefix/contains return nothing, the trigram tier runs and maps results."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        # Tier order: exact, prefix, contains (all empty) -> trigram (one fuzzy hit).
        # Trigram rows carry 8 columns: curie, name, namespace, definition, type,
        # synonyms(array), name_score, synonym_score.
        mock_execute.fetchall.side_effect = [
            [],  # Tier 1 exact
            [],  # Tier 2 prefix
            [],  # Tier 3 contains
            [
                (
                    "WBbt:0005190",
                    "amphid ciliated sensory neuron",
                    "anatomy",
                    "a sensory neuron",
                    "WBBTTerm",
                    ["ASN"],
                    0.62,  # name_score
                    0.0,  # synonym_score
                )
            ],
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="ciliated neuron", ontology_type="WBBTTerm", limit=20
        )

        # All four tiers should have executed
        self.assertEqual(mock_session.execute.call_count, 4)
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertIsInstance(r, OntologyTermResult)
        self.assertEqual(r.curie, "WBbt:0005190")
        self.assertEqual(r.match_type, "trigram")
        self.assertEqual(r.matched_field, "name")
        self.assertAlmostEqual(r.match_score, 0.62)
        mock_session.close.assert_called_once()

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_tier_skipped_when_limit_filled(self, mock_session_factory):
        """When an earlier tier already satisfies the limit, the trigram tier is not run."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        # Exact tier alone fills limit=1, so no further tiers should execute.
        mock_execute.fetchall.side_effect = [
            # 6 cols (curie, name, namespace, definition, type, synonyms): non-trigram
            # tiers do NOT carry name_score/synonym_score columns.
            [("WBbt:1", "neuron", "anatomy", "d", "WBBTTerm", [])],  # Tier 1 exact (6 cols)
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="neuron", ontology_type="WBBTTerm", limit=1
        )

        self.assertEqual(mock_session.execute.call_count, 1)  # only the exact tier ran
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].match_type, "exact")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_matched_field_prefers_higher_score(self, mock_session_factory):
        """matched_field/match_score follow the field (name vs synonym) with the higher score."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [],  # exact
            [],  # prefix
            [],  # contains
            [
                (
                    "WBbt:0005062",
                    "linker cell",
                    "anatomy",
                    None,
                    "WBBTTerm",
                    ["lc", "linker"],
                    0.40,  # name_score
                    0.71,  # synonym_score (higher -> matched_field='synonym')
                )
            ],
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="linker", ontology_type="WBBTTerm", limit=20
        )

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.matched_field, "synonym")
        self.assertAlmostEqual(r.match_score, 0.71)
        self.assertEqual(r.match_type, "trigram")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_exact_match_path_does_not_run_trigram(self, mock_session_factory):
        """exact_match=True must only run the exact tier (never the fuzzy trigram tier)."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [],  # Tier 1 exact (empty); exact_match=True must not fall through to fuzzy tiers
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="ciliated neuron", ontology_type="WBBTTerm", exact_match=True, limit=20
        )

        self.assertEqual(mock_session.execute.call_count, 1)
        self.assertEqual(results, [])

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_tie_break_prefers_name(self, mock_session_factory):
        """Equal name/synonym scores resolve to matched_field='name' (stable default)."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [],  # exact
            [],  # prefix
            [],  # contains
            [
                (
                    "WBbt:0005394",
                    "amphid neuron",
                    "anatomy",
                    None,
                    "WBBTTerm",
                    ["amphid"],
                    0.5,  # name_score
                    0.5,  # synonym_score (tie -> matched_field='name')
                )
            ],
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="amphid neuron", ontology_type="WBBTTerm", limit=20
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].matched_field, "name")
        self.assertAlmostEqual(results[0].match_score, 0.5)

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_null_synonym_score_from_db_is_handled(self, mock_session_factory):
        """A NULL synonym_score (term with no synonyms) must not crash; treated as 0.0."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [],  # exact
            [],  # prefix
            [],  # contains
            [
                (
                    "WBbt:0005334",
                    "AS neuron",
                    "anatomy",
                    None,
                    "WBBTTerm",
                    [],
                    0.44,  # name_score
                    None,  # synonym_score NULL from DB (no synonyms) -> Python guard -> 0.0
                )
            ],
        ]
        mock_session.execute.return_value = mock_execute

        results = self.db.search_ontology_terms(
            term="AS neuron", ontology_type="WBBTTerm", limit=20
        )

        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r.matched_field, "name")
        self.assertAlmostEqual(r.match_score, 0.44)
        self.assertEqual(r.match_type, "trigram")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_trigram_sql_uses_word_similarity_and_bound_threshold(self, mock_session_factory):
        """The generated Tier 4 SQL must call word_similarity() and bind the threshold.

        The other tiers are mocked, so this is the only guard against the Tier 4 query
        silently regressing (e.g. losing word_similarity or the threshold param) without
        a live database.
        """
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [[], [], [], []]  # all four tiers empty
        mock_session.execute.return_value = mock_execute

        self.db.search_ontology_terms(term="ciliated neuron", ontology_type="WBBTTerm", limit=20)

        # The 4th execute call is the trigram tier.
        self.assertEqual(mock_session.execute.call_count, 4)
        trigram_call = mock_session.execute.call_args_list[3]
        sql_text = str(trigram_call.args[0])
        params = trigram_call.args[1]
        self.assertIn("word_similarity", sql_text)
        self.assertEqual(params["threshold"], 0.3)
        self.assertEqual(params["search_text"], "CILIATED NEURON")
        self.assertEqual(params["ontology_type"], "WBBTTerm")


if __name__ == "__main__":
    unittest.main()
