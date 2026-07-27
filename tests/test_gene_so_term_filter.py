#!/usr/bin/env python
"""Unit tests for the SO gene-type filter on get_genes_raw.

These mock the SQLAlchemy session so they run without a live database, in the same
style as tests/test_ontology_trigram_search.py.

The assertions deliberately pin the SQL *operators*, not just the identifiers.
Three properties of this predicate are subtle enough to be worth locking down, and
a test that only checks for the presence of "is_a" or "EXISTS" still passes when
any of them is broken:

  - The roots must be matched directly (``gt.curie IN``) as well as through the
    closure, because ontologytermclosure has no distance-0 self row. A closure-only
    predicate drops every gene typed as exactly "gene" or exactly "pseudogene".
  - closuretypes must be compared with ``=`` and not a containment operator. Every
    ancestor appears as both ["is_a"] and ["is_a","part_of"]; ``@>`` matches the
    mixed rows too and inflates the gene subtree from 137 to 246 terms by walking
    part_of paths.
  - The disjunction must be its own parenthesized group, or ``gt.obsolete = false``
    binds to only the first branch.
"""

import re
import unittest
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy.dialects import postgresql

from agr_curation_api.db_methods import (
    DatabaseMethods,
    DatabaseConfig,
    GENE_SO_TERM_CURIE,
    GENE_LIKE_SO_TERM_CURIES,
)

# The full predicate, whitespace-normalized. Asserting on this as one string pins the
# operators, the correlation to the outer gt.id, the closure direction and the
# parenthesization together.
EXPECTED_PREDICATE = (
    "AND gt.obsolete = false "
    "AND ( gt.curie IN :so_terms "
    "OR EXISTS ( SELECT 1 "
    "FROM ontologytermclosure otc "
    "JOIN ontologyterm gt_ancestor ON gt_ancestor.id = otc.closureobject_id "
    "WHERE otc.closuresubject_id = gt.id "
    "AND otc.closuretypes = '[\"is_a\"]'::jsonb "
    "AND gt_ancestor.curie IN :so_terms ) )"
)


def normalize(sql):
    """Collapse whitespace and restore the expanding bindparam's original name.

    SQLAlchemy renders an expanding bindparam as ``(__[POSTCOMPILE_so_terms])``;
    folding it back to ``:so_terms`` keeps the expected predicate readable.
    """
    collapsed = re.sub(r"\s+", " ", sql).strip()
    return collapsed.replace("(__[POSTCOMPILE_so_terms])", ":so_terms")


def render_postgres(stmt, params):
    """Compile a statement through the real PostgreSQL dialect, expanding IN lists.

    Asserting on ``str(stmt)`` alone cannot see whether the expanding bindparam is
    still attached, because the mocked session never executes. Compiling here does:
    a statement that lost the bindparam renders an unexpanded
    ``__[POSTCOMPILE_so_terms]`` marker and binds no values.
    """
    compiled = stmt.params(**params).compile(
        dialect=postgresql.dialect(), compile_kwargs={"render_postcompile": True}
    )
    return re.sub(r"\s+", " ", str(compiled)).strip(), dict(compiled.params)


class TestGeneSOTermFilter(unittest.TestCase):
    """Test suite for gene-type filtering in get_genes_raw."""

    def setUp(self):
        """Create a DatabaseMethods instance with engine/sessionmaker mocked out."""
        self.mock_config = Mock(spec=DatabaseConfig)
        self.mock_config.connection_string = "postgresql://test:test@localhost/test"
        with patch("agr_curation_api.db_methods.create_engine"), patch(
            "agr_curation_api.db_methods.sessionmaker"
        ):
            self.db = DatabaseMethods(self.mock_config)

    def _run(self, **kwargs):
        """Call get_genes_raw with a mocked session; return (sql_text, params, result)."""
        with patch.object(DatabaseMethods, "_create_session") as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_execute = MagicMock()
            mock_execute.fetchall.return_value = [("WB:WBGene00001044", "unc-13")]
            mock_session.execute.return_value = mock_execute

            result = self.db.get_genes_raw("NCBITaxon:6239", **kwargs)

        sql_text, params = mock_session.execute.call_args[0]
        self.stmt = sql_text
        return normalize(str(sql_text)), params, result

    def test_default_restricts_to_gene_subtree(self):
        """The default include list is SO "gene" alone, plus its is_a descendants."""
        sql, params, _ = self._run()
        self.assertEqual(params["so_terms"], [GENE_SO_TERM_CURIE])
        self.assertEqual(GENE_SO_TERM_CURIE, "SO:0000704")
        self.assertIn("genetype_id", sql)

    def test_gene_like_curies_covers_the_three_roots_outside_the_gene_subtree(self):
        """The opt-in wider list adds the roots no is_a path from "gene" can reach.

        pseudogene, gene_segment and heritable_phenotypic_marker are not is_a
        descendants of SO:0000704, so a caller wanting them (the gene descriptions
        pipeline) has to name them; this constant is what it should pass.
        """
        self.assertEqual(
            list(GENE_LIKE_SO_TERM_CURIES),
            ["SO:0000704", "SO:0000336", "SO:3000000", "SO:0001500"],
        )
        _, params, _ = self._run(so_terms=GENE_LIKE_SO_TERM_CURIES)
        self.assertEqual(params["so_terms"], list(GENE_LIKE_SO_TERM_CURIES))

    def test_full_closure_predicate_is_emitted_verbatim(self):
        """The whole gene-type predicate, operators included."""
        sql, _, _ = self._run()
        self.assertIn(EXPECTED_PREDICATE, sql)

    def test_only_pure_is_a_closure_rows_are_followed(self):
        """closuretypes uses exact equality, so part_of paths cannot leak in.

        A containment test would also match the ["is_a","part_of"] rows.
        """
        sql, _, _ = self._run()
        self.assertIn("otc.closuretypes = '[\"is_a\"]'::jsonb", sql)
        self.assertNotIn("@>", sql)
        self.assertNotIn("<@", sql)
        self.assertNotIn("closuretypes ?", sql)
        self.assertNotIn("jsonb_array_elements", sql)
        self.assertNotIn("part_of", sql)

    def test_roots_matched_explicitly_because_closure_is_not_reflexive(self):
        """The requested terms themselves must match, not only their descendants."""
        sql, _, _ = self._run()
        self.assertIn("gt.curie IN :so_terms OR EXISTS", sql)

    def test_closure_is_a_correlated_exists_not_a_join(self):
        """EXISTS, correlated to the outer gt — a JOIN would duplicate gene rows."""
        sql, _, _ = self._run()
        self.assertIn("WHERE otc.closuresubject_id = gt.id", sql)
        self.assertIn("gt_ancestor.id = otc.closureobject_id", sql)
        self.assertNotIn("JOIN ontologytermclosure", sql)
        self.assertNotIn("DISTINCT", sql)

    def test_obsolete_filter_binds_outside_the_disjunction(self):
        """Obsolete SO gene types must not match (e.g. TSS_region, SO:0001240).

        Inside the OR group the exclusion would apply to only one branch.
        """
        sql, _, _ = self._run()
        self.assertIn("AND gt.obsolete = false AND (", sql)

    def test_explicit_so_terms_are_passed_through(self):
        """An explicit include list reaches the query unchanged."""
        roots = ["SO:0000704", "SO:0000336"]
        _, params, _ = self._run(so_terms=roots)
        self.assertEqual(params["so_terms"], roots)

    def test_include_descendants_false_drops_closure(self):
        """Exact-match-only mode keeps the curie filter but not the closure lookup."""
        sql, params, _ = self._run(so_terms=["SO:0000704"], include_descendants=False)
        self.assertEqual(params["so_terms"], ["SO:0000704"])
        self.assertIn("AND gt.obsolete = false AND gt.curie IN :so_terms", sql)
        self.assertNotIn("ontologytermclosure", sql)

    def test_empty_so_terms_disables_gene_type_filtering(self):
        """An explicitly empty list opts out of gene-type filtering entirely."""
        sql, params, _ = self._run(so_terms=[])
        self.assertNotIn("so_terms", params)
        self.assertNotIn("genetype_id", sql)
        self.assertNotIn("ontologytermclosure", sql)
        self.assertNotIn("gt.obsolete", sql)

    def test_bare_string_so_terms_is_rejected(self):
        """A str satisfies Sequence[str], so it would otherwise match per character."""
        with self.assertRaises(ValueError) as ctx:
            self._run(so_terms="SO:0000704")
        self.assertIn("sequence of SO CURIEs", str(ctx.exception))

    def test_rows_are_mapped_to_gene_id_and_symbol(self):
        """The returned shape is unchanged by the filter."""
        _, _, result = self._run()
        self.assertEqual(result, [{"gene_id": "WB:WBGene00001044", "gene_symbol": "unc-13"}])

    def test_pagination_still_applied(self):
        """limit/offset continue to be appended after the filter."""
        sql, _, _ = self._run(limit=10, offset=5)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("OFFSET 5", sql)

    def test_statement_compiles_with_the_expanding_param_intact(self):
        """The bound so_terms list really expands once compiled for PostgreSQL."""
        _, params, _ = self._run(limit=10, so_terms=GENE_LIKE_SO_TERM_CURIES)
        rendered, bound = render_postgres(self.stmt, params)
        self.assertNotIn("POSTCOMPILE", rendered)
        self.assertEqual(len([k for k in bound if k.startswith("so_terms_")]), 4)
        self.assertIn(
            "gt.curie IN (%(so_terms_1)s, %(so_terms_2)s, %(so_terms_3)s, %(so_terms_4)s)",
            rendered,
        )


class TestGeneSOTermFilterByTaxon(unittest.TestCase):
    """The same filter on get_genes_by_taxon, which is what client.get_genes uses.

    get_genes_raw and get_genes_by_taxon are siblings returning the same genes in
    different shapes, so they must agree on which rows count as genes.
    """

    def setUp(self):
        """Create a DatabaseMethods instance with engine/sessionmaker mocked out."""
        self.mock_config = Mock(spec=DatabaseConfig)
        self.mock_config.connection_string = "postgresql://test:test@localhost/test"
        with patch("agr_curation_api.db_methods.create_engine"), patch(
            "agr_curation_api.db_methods.sessionmaker"
        ):
            self.db = DatabaseMethods(self.mock_config)

    def _run(self, **kwargs):
        """Call get_genes_by_taxon with a mocked session; return (sql, params, result)."""
        with patch.object(DatabaseMethods, "_create_session") as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_execute = MagicMock()
            mock_execute.fetchall.return_value = [("WB:WBGene00001044", "unc-13")]
            mock_session.execute.return_value = mock_execute

            result = self.db.get_genes_by_taxon("NCBITaxon:6239", **kwargs)

        sql_text, params = mock_session.execute.call_args[0]
        self.stmt = sql_text
        return normalize(str(sql_text)), params, result

    def test_default_restricts_to_gene_subtree(self):
        """The default include list is SO "gene" alone, plus its is_a descendants."""
        sql, params, _ = self._run()
        self.assertEqual(params["so_terms"], [GENE_SO_TERM_CURIE])
        self.assertIn("genetype_id", sql)

    def test_full_closure_predicate_is_emitted_verbatim(self):
        """The identical gene-type predicate, operators included."""
        sql, _, _ = self._run()
        self.assertIn(EXPECTED_PREDICATE, sql)

    def test_predicate_matches_get_genes_raw(self):
        """Both sibling methods emit the same gene-type predicate.

        They differ elsewhere (be.internal, obsolete handling, return shape), but a
        divergence in gene-ness would make the two disagree on the gene count.
        """
        by_taxon_sql, by_taxon_params, _ = self._run()

        with patch.object(DatabaseMethods, "_create_session") as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_execute = MagicMock()
            mock_execute.fetchall.return_value = []
            mock_session.execute.return_value = mock_execute
            self.db.get_genes_raw("NCBITaxon:6239")
        raw_sql = normalize(str(mock_session.execute.call_args[0][0]))
        raw_params = mock_session.execute.call_args[0][1]

        self.assertIn(EXPECTED_PREDICATE, by_taxon_sql)
        self.assertIn(EXPECTED_PREDICATE, raw_sql)
        self.assertEqual(by_taxon_params["so_terms"], raw_params["so_terms"])

    def test_explicit_so_terms_are_passed_through(self):
        """The wider include list reaches the query unchanged."""
        _, params, _ = self._run(so_terms=GENE_LIKE_SO_TERM_CURIES)
        self.assertEqual(params["so_terms"], list(GENE_LIKE_SO_TERM_CURIES))

    def test_empty_so_terms_disables_gene_type_filtering(self):
        """An explicitly empty list opts out of gene-type filtering entirely."""
        sql, params, _ = self._run(so_terms=[])
        self.assertNotIn("so_terms", params)
        self.assertNotIn("genetype_id", sql)
        self.assertNotIn("ontologytermclosure", sql)

    def test_include_descendants_false_drops_closure(self):
        """Exact-match-only mode keeps the curie filter but not the closure lookup."""
        sql, _, _ = self._run(so_terms=["SO:0000704"], include_descendants=False)
        self.assertIn("gt.curie IN :so_terms", sql)
        self.assertNotIn("ontologytermclosure", sql)

    def test_bare_string_so_terms_is_rejected(self):
        """A str satisfies Sequence[str], so it would otherwise match per character."""
        with self.assertRaises(ValueError) as ctx:
            self._run(so_terms="SO:0000704")
        self.assertIn("sequence of SO CURIEs", str(ctx.exception))

    def test_pagination_survives_the_bound_so_terms_param(self):
        """limit/offset are appended before text(), so the expanding bindparam holds.

        Rebuilding the statement as text(str(stmt) + " LIMIT n") after binding — the
        pattern this query used before the filter existed — silently discards the
        so_terms binding. Compiling for real is what catches that; the SQL string
        looks identical either way.
        """
        sql, params, _ = self._run(limit=10, offset=5, so_terms=GENE_LIKE_SO_TERM_CURIES)
        self.assertIn("LIMIT 10", sql)
        self.assertIn("OFFSET 5", sql)
        self.assertIn(EXPECTED_PREDICATE, sql)

        rendered, bound = render_postgres(self.stmt, params)
        self.assertNotIn("POSTCOMPILE", rendered)
        self.assertEqual(
            bound,
            {
                "species_taxon": "NCBITaxon:6239",
                "so_terms_1": "SO:0000704",
                "so_terms_2": "SO:0000336",
                "so_terms_3": "SO:3000000",
                "so_terms_4": "SO:0001500",
            },
        )
        # Both references to the one expanding param expand to the same placeholders.
        self.assertEqual(rendered.count("%(so_terms_4)s"), 2)

    def test_include_obsolete_does_not_relax_the_gene_type_filter(self):
        """Obsolete SO gene types stay excluded even when obsolete genes are wanted."""
        sql, _, _ = self._run(include_obsolete=True)
        self.assertIn(EXPECTED_PREDICATE, sql)
        self.assertNotIn("be.obsolete = false", sql)

    def test_rows_are_mapped_to_gene_objects(self):
        """The returned shape is unchanged by the filter."""
        _, _, result = self._run()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].primaryExternalId, "WB:WBGene00001044")
        self.assertEqual(result[0].geneSymbol.displayText, "unc-13")


if __name__ == "__main__":
    unittest.main()
