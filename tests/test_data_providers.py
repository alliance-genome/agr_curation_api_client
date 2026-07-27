#!/usr/bin/env python3
"""Test get_data_providers() against the persistent store database.

Regression coverage for SCRUM-6195: the species table no longer has an
``assembly_curie`` column; the query must filter on the ``genomeassembly_id``
foreign key introduced by the new genome-assembly data model.
"""

import os

import pytest

from agr_curation_api.db_methods import DatabaseMethods

pytestmark = pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)

# MOD data providers that always carry a canonical genome assembly.
EXPECTED_PROVIDERS = {"WB", "MGI", "RGD", "SGD", "FB", "ZFIN", "HUMAN"}


class TestGetDataProviders:
    """Tests for DatabaseMethods.get_data_providers()."""

    def test_returns_expected_data_providers(self):
        db = DatabaseMethods()
        try:
            results = db.get_data_providers()
        finally:
            db.close()

        assert results, "get_data_providers() should return at least one provider"

        # Each entry is a (display_name, taxon_curie) tuple.
        for display_name, taxon_curie in results:
            assert display_name, "display_name should be non-empty"
            assert taxon_curie.startswith("NCBITaxon:"), (
                f"taxon_curie should be an NCBITaxon CURIE, got {taxon_curie!r}"
            )

        display_names = {display_name for display_name, _ in results}
        missing = EXPECTED_PROVIDERS - display_names
        assert not missing, f"Expected data providers missing from results: {missing}"
