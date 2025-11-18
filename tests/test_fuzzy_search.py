#!/usr/bin/env python
"""Unit tests for entity search functionality in DatabaseMethods."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from agr_curation_api.db_methods import DatabaseMethods, DatabaseConfig
from agr_curation_api.exceptions import AGRAPIError


class TestEntitySearch(unittest.TestCase):
    """Test suite for search_entities method."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock database config
        self.mock_config = Mock(spec=DatabaseConfig)
        self.mock_config.connection_string = "postgresql://test:test@localhost/test"

        # Create DatabaseMethods instance with mocked dependencies
        with patch("agr_curation_api.db_methods.create_engine"), patch("agr_curation_api.db_methods.sessionmaker"):
            self.db_methods = DatabaseMethods(self.mock_config)

    def test_empty_search_pattern_returns_empty_list(self):
        """Test that empty search pattern returns empty list."""
        result = self.db_methods.search_entities(entity_type="gene", search_pattern="", taxon_curie="NCBITaxon:7227")
        self.assertEqual(result, [])

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_gene_fuzzy_search_includes_synonyms_by_default(self, mock_session_factory):
        """Test that gene search includes synonyms by default."""
        # Mock session and execute
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Mock query results for tiered search (exact, prefix, contains)
        # Tier 1 (exact): finds 'rut'
        # Tier 2 (prefix): finds 'rutabaga'
        # Tier 3 (contains): no additional results
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [("FB:FBgn0003301", False, "rut", "exact", 1)],  # Exact match
            [("FB:FBgn0003301", False, "rutabaga", "starts_with", 2)],  # Prefix match
            [],  # Contains match (no additional results)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="gene", search_pattern="rut", taxon_curie="NCBITaxon:7227", include_synonyms=True
        )

        # Verify results structure
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["entity_curie"], "FB:FBgn0003301")
        self.assertEqual(result[0]["entity"], "rut")
        self.assertEqual(result[0]["match_type"], "exact")
        self.assertEqual(result[0]["relevance"], 1)

        # Verify session was used correctly (3 queries for tiered search)
        self.assertEqual(mock_session.execute.call_count, 3)
        mock_session.close.assert_called_once()

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_allele_fuzzy_search_works(self, mock_session_factory):
        """Test that allele entity search works correctly."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Tiered search: no exact, finds prefix, no contains
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [],  # Exact match (no results)
            [("FB:FBal0014878", False, "Adcy1<sup>rut-1</sup>", "starts_with", 2)],  # Prefix match
            [],  # Contains match (no additional results)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="allele", search_pattern="Adcy1", taxon_curie="NCBITaxon:7227"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entity_curie"], "FB:FBal0014878")
        self.assertEqual(result[0]["match_type"], "starts_with")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_agm_fuzzy_search_works(self, mock_session_factory):
        """Test that AGM entity search works correctly."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Tiered search: finds exact, no prefix/contains needed
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [("ZFIN:ZDB-FISH-123", False, "wild type", "exact", 1)],  # Exact match
            [],  # Prefix match (not executed due to limit reached)
            [],  # Contains match (not executed due to limit reached)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="agm", search_pattern="wild type", taxon_curie="NCBITaxon:7955"
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["entity_curie"], "ZFIN:ZDB-FISH-123")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_exclude_synonyms_flag_works(self, mock_session_factory):
        """Test that include_synonyms=False excludes synonyms."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Tiered search: finds exact match
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [("FB:FBgn0003301", False, "Adcy1", "exact", 1)],  # Exact match
            [],  # Prefix match (not executed due to limit reached)
            [],  # Contains match (not executed due to limit reached)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="gene", search_pattern="Adcy1", taxon_curie="NCBITaxon:7227", include_synonyms=False
        )

        # Verify query was called (synonyms would be excluded in SQL)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(mock_session.execute.call_count, 1)

        # Verify the SQL doesn't include synonym annotation types
        call_args = mock_session.execute.call_args_list[0]  # Check first call (exact match)
        sql_text = str(call_args[0][0])
        # When include_synonyms=False, GeneSynonymSlotAnnotation shouldn't be in query
        self.assertNotIn("GeneSynonymSlotAnnotation", sql_text)

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_limit_parameter_works(self, mock_session_factory):
        """Test that limit parameter restricts results."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Tiered search: exact finds 2, prefix finds 3, total=5 (limit respected)
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [(f"FB:FBgn{i:08d}", False, f"gene{i}", "exact", 1) for i in range(2)],  # Exact: 2 results
            [(f"FB:FBgn{i:08d}", False, f"gene{i}", "starts_with", 2) for i in range(2, 5)],  # Prefix: 3 results
            [],  # Contains (not needed, limit reached at 5)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="gene", search_pattern="gene", taxon_curie="NCBITaxon:7227", limit=5
        )

        # Verify results returned respect limit
        self.assertEqual(len(result), 5)

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_relevance_ordering_in_results(self, mock_session_factory):
        """Test that results include relevance scoring."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Mock results with different relevance scores
        mock_session.execute.return_value.fetchall.return_value = [
            ("FB:FBgn0001", False, "rut", "exact", 1),
            ("FB:FBgn0001", False, "rutabaga", "starts_with", 2),
            ("FB:FBgn0002", False, "scrutinize", "contains", 3),
        ]

        result = self.db_methods.search_entities(entity_type="gene", search_pattern="rut", taxon_curie="NCBITaxon:7227")

        # Verify relevance scores are in results
        self.assertEqual(result[0]["relevance"], 1)  # exact
        self.assertEqual(result[1]["relevance"], 2)  # starts_with
        self.assertEqual(result[2]["relevance"], 3)  # contains

        # Verify match types
        self.assertEqual(result[0]["match_type"], "exact")
        self.assertEqual(result[1]["match_type"], "starts_with")
        self.assertEqual(result[2]["match_type"], "contains")

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_unsupported_entity_type_raises_error(self, mock_session_factory):
        """Test that unsupported entity types raise AGRAPIError."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        with self.assertRaises(AGRAPIError) as context:
            self.db_methods.search_entities(
                entity_type="invalid_type", search_pattern="test", taxon_curie="NCBITaxon:7227"
            )

        self.assertIn("Unsupported entity_type", str(context.exception))

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_database_error_handling(self, mock_session_factory):
        """Test that database errors are caught and re-raised as AGRAPIError."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Simulate database error
        mock_session.execute.side_effect = Exception("Database connection failed")

        with self.assertRaises(AGRAPIError) as context:
            self.db_methods.search_entities(entity_type="gene", search_pattern="test", taxon_curie="NCBITaxon:7227")

        self.assertIn("Database query failed", str(context.exception))

        # Verify session was closed even after error
        mock_session.close.assert_called_once()

    @patch("agr_curation_api.db_methods.DatabaseMethods._create_session")
    def test_case_insensitive_search(self, mock_session_factory):
        """Test that search is case-insensitive."""
        mock_session = MagicMock()
        mock_session_factory.return_value = mock_session

        # Tiered search: all 3 results found in exact match tier
        mock_execute = MagicMock()
        mock_execute.fetchall.side_effect = [
            [  # Exact match tier
                ("FB:FBgn0003301", False, "rut", "exact", 1),
                ("FB:FBgn0003301", False, "RUT", "exact", 1),
                ("FB:FBgn0003301", False, "Rut", "exact", 1),
            ],
            [],  # Prefix match (not needed)
            [],  # Contains match (not needed)
        ]
        mock_session.execute.return_value = mock_execute

        result = self.db_methods.search_entities(
            entity_type="gene", search_pattern="rut", taxon_curie="NCBITaxon:7227"  # lowercase
        )

        # Verify all case variations are found
        self.assertEqual(len(result), 3)

        # Verify search was uppercased in parameters (check first call)
        call_args = mock_session.execute.call_args_list[0]
        params = call_args[0][1]
        self.assertEqual(params["search_exact"], "RUT")  # Uppercase


if __name__ == "__main__":
    unittest.main()
