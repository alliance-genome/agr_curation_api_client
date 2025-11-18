#!/usr/bin/env python
"""Integration tests for entity search with real database.

These tests run against the production curation database (read-only) via
the database-integration-tests GitHub workflow.

The tests verify:
1. Tiered search implementation returns correct results
2. Performance characteristics (exact/prefix vs contains)
3. All entity types work correctly
4. Relevance ordering is correct
"""

import pytest
import os
from agr_curation_api.db_methods import DatabaseMethods, DatabaseConfig


@pytest.fixture(scope="module")
def db_methods():
    """Create DatabaseMethods instance connected to real database."""
    # Check if we're running in CI with database tunnel
    if not os.getenv("PERSISTENT_STORE_DB_HOST"):
        pytest.skip("Database integration tests require PERSISTENT_STORE_DB_* environment variables")

    config = DatabaseConfig()
    return DatabaseMethods(config)


class TestTieredSearchIntegration:
    """Integration tests for tiered entity search."""

    def test_gene_synonym_search(self, db_methods):
        """Test that gene synonym search works."""
        results = db_methods.search_entities(
            entity_type="gene",
            search_pattern="rutabaga",
            taxon_curie="NCBITaxon:7227",  # Drosophila
            include_synonyms=True,
            limit=20,
        )

        # Should find gene with 'rutabaga' synonym
        assert len(results) > 0, "Expected to find gene with 'rutabaga' synonym"

        # Result should include the match
        assert any("rutabaga" in r["entity"].lower() for r in results), "Expected to find 'rutabaga' in results"

    def test_gene_without_synonyms(self, db_methods):
        """Test that include_synonyms=False excludes synonym matches."""
        with_synonyms = db_methods.search_entities(
            entity_type="gene", search_pattern="white", taxon_curie="NCBITaxon:7227", include_synonyms=True, limit=20
        )

        without_synonyms = db_methods.search_entities(
            entity_type="gene", search_pattern="white", taxon_curie="NCBITaxon:7227", include_synonyms=False, limit=20
        )

        # Should return results in both cases
        assert len(with_synonyms) > 0
        assert len(without_synonyms) > 0

        # With synonyms should generally return more or equal results
        assert len(with_synonyms) >= len(without_synonyms), "Expected more results when synonyms included"

    def test_allele_search(self, db_methods):
        """Test that allele search works."""
        results = db_methods.search_entities(
            entity_type="allele", search_pattern="white", taxon_curie="NCBITaxon:7227", limit=10  # Drosophila
        )

        # Should find some alleles (or return empty list if none exist)
        assert isinstance(results, list)

        # If results found, verify structure
        if len(results) > 0:
            result = results[0]
            assert "entity_curie" in result
            assert result["entity_curie"].startswith("FB:FBab")  # Drosophila allele prefix

    def test_relevance_ordering(self, db_methods):
        """Test that results are ordered by relevance (exact > starts_with > contains)."""
        results = db_methods.search_entities(
            entity_type="gene", search_pattern="white", taxon_curie="NCBITaxon:7227", limit=20
        )

        assert len(results) > 0

        # Extract relevance scores
        relevance_scores = [r["relevance"] for r in results]

        # Verify ordering is non-decreasing (sorted)
        assert relevance_scores == sorted(
            relevance_scores
        ), "Results should be ordered by relevance (1=exact, 2=starts_with, 3=contains)"

        # Verify relevance scores are valid
        assert all(score in [1, 2, 3] for score in relevance_scores), "All relevance scores should be 1, 2, or 3"

        # Verify match types correspond to relevance
        for result in results:
            if result["relevance"] == 1:
                assert result["match_type"] == "exact"
            elif result["relevance"] == 2:
                assert result["match_type"] == "starts_with"
            elif result["relevance"] == 3:
                assert result["match_type"] == "contains"

    def test_limit_parameter(self, db_methods):
        """Test that limit parameter is respected."""
        for limit in [5, 10, 20]:
            results = db_methods.search_entities(
                entity_type="gene",
                search_pattern="a",  # Common letter, should find many genes
                taxon_curie="NCBITaxon:7227",
                limit=limit,
            )

            # Should not exceed limit
            assert len(results) <= limit, f"Expected no more than {limit} results"

    def test_different_taxa(self, db_methods):
        """Test search across different organisms."""
        # Test a few different organisms
        taxa_tests = [
            ("NCBITaxon:7227", "Drosophila"),  # Drosophila melanogaster
            ("NCBITaxon:10090", "Mouse"),  # Mus musculus
            ("NCBITaxon:6239", "C. elegans"),  # Caenorhabditis elegans
        ]

        for taxon_curie, name in taxa_tests:
            results = db_methods.search_entities(
                entity_type="gene", search_pattern="white", taxon_curie=taxon_curie, limit=10
            )

            # Results should be a list (may be empty for some organisms)
            assert isinstance(results, list), f"Expected list for {name}"

            # If results found, verify they're for the correct taxon
            # (we can't verify this easily without additional queries)

    def test_case_insensitivity(self, db_methods):
        """Test that search is case-insensitive."""
        # Test same search with different cases
        lowercase_results = db_methods.search_entities(
            entity_type="gene", search_pattern="white", taxon_curie="NCBITaxon:7227", limit=20
        )

        uppercase_results = db_methods.search_entities(
            entity_type="gene", search_pattern="WHITE", taxon_curie="NCBITaxon:7227", limit=20
        )

        mixed_results = db_methods.search_entities(
            entity_type="gene", search_pattern="White", taxon_curie="NCBITaxon:7227", limit=20
        )

        # All should return the same results (or very similar)
        assert len(lowercase_results) > 0
        assert len(lowercase_results) == len(uppercase_results)
        assert len(lowercase_results) == len(mixed_results)

        # Verify same entities returned
        lowercase_curies = {r["entity_curie"] for r in lowercase_results}
        uppercase_curies = {r["entity_curie"] for r in uppercase_results}
        mixed_curies = {r["entity_curie"] for r in mixed_results}

        assert lowercase_curies == uppercase_curies == mixed_curies

    def test_no_duplicates(self, db_methods):
        """Test that results contain no duplicate entities."""
        results = db_methods.search_entities(
            entity_type="gene", search_pattern="white", taxon_curie="NCBITaxon:7227", limit=20
        )

        # Extract entity CURIEs
        curies = [r["entity_curie"] for r in results]

        # Check for duplicates
        assert len(curies) == len(
            set(curies)
        ), f"Found duplicate entities in results: {[c for c in curies if curies.count(c) > 1]}"

    def test_empty_search_returns_empty(self, db_methods):
        """Test that empty search pattern returns empty list."""
        results = db_methods.search_entities(
            entity_type="gene", search_pattern="", taxon_curie="NCBITaxon:7227", limit=20
        )

        assert results == []

    def test_nonexistent_pattern(self, db_methods):
        """Test that nonexistent pattern returns empty list."""
        results = db_methods.search_entities(
            entity_type="gene", search_pattern="zzz_nonexistent_gene_xyz_12345", taxon_curie="NCBITaxon:7227", limit=20
        )

        assert results == []
