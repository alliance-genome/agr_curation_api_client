#!/usr/bin/env python
"""Tests for the closure direction in get_ontology_ancestors_or_descendants (SCRUM-6787).

ontologytermclosure stores closuresubject_id as the descendant and closureobject_id as
the ancestor. The ancestors branch used to join exactly like the descendants branch, so
both directions returned descendants. The unit tests mock the SQLAlchemy session, in the
same style as tests/test_gene_so_term_filter.py, and pin which closure column each
direction matches the node on and which one it returns. The live test checks real rows.
"""

import os
import re
import unittest
from unittest.mock import Mock, patch, MagicMock

import pytest

from agr_curation_api.db_methods import DatabaseMethods, DatabaseConfig


def normalize(sql):
    return re.sub(r"\s+", " ", sql).strip()


class TestOntologyClosureDirection(unittest.TestCase):

    def setUp(self):
        """Create a DatabaseMethods instance with engine/sessionmaker mocked out."""
        self.mock_config = Mock(spec=DatabaseConfig)
        self.mock_config.connection_string = "postgresql://test:test@localhost/test"
        with patch("agr_curation_api.db_methods.create_engine"), patch(
            "agr_curation_api.db_methods.sessionmaker"
        ):
            self.db = DatabaseMethods(self.mock_config)

    def _run(self, direction):
        """Call the method with a mocked session; return (sql_text, params, result)."""
        with patch.object(DatabaseMethods, "_create_session") as mock_session_factory:
            mock_session = MagicMock()
            mock_session_factory.return_value = mock_session
            mock_execute = MagicMock()
            mock_execute.fetchall.return_value = [("ATP:0000009",)]
            mock_session.execute.return_value = mock_execute

            result = self.db.get_ontology_ancestors_or_descendants("ATP:0000079", direction)

        sql_text, params = mock_session.execute.call_args[0]
        return normalize(str(sql_text)), params, result

    def test_descendants_return_the_subject_side(self):
        sql, params, result = self._run("descendants")
        self.assertIn("JOIN ontologytermclosure otc ON ot.id = otc.closuresubject_id", sql)
        self.assertIn("JOIN ontologyterm ancestor ON ancestor.id = otc.closureobject_id", sql)
        self.assertIn("WHERE ancestor.curie = :ontology_node", sql)
        self.assertEqual(params, {"ontology_node": "ATP:0000079"})
        self.assertEqual(result, ["ATP:0000009"])

    def test_ancestors_return_the_object_side(self):
        sql, params, result = self._run("ancestors")
        self.assertIn("JOIN ontologytermclosure otc ON ot.id = otc.closureobject_id", sql)
        self.assertIn("JOIN ontologyterm descendant ON descendant.id = otc.closuresubject_id", sql)
        self.assertIn("WHERE descendant.curie = :ontology_node", sql)
        self.assertEqual(params, {"ontology_node": "ATP:0000079"})
        self.assertEqual(result, ["ATP:0000009"])


@pytest.mark.skipif(
    not os.getenv("PERSISTENT_STORE_DB_HOST"),
    reason="Database integration tests require PERSISTENT_STORE_DB_* environment variables",
)
def test_closure_direction_against_live_curation_db():
    """ATP:0000079 (genetic phenotype) sits under phenotype -> topic tag -> alliance tag
    for publication, and has RNAi/variation/overexpression phenotype below it."""
    db = DatabaseMethods()
    ancestors = set(db.get_ontology_ancestors_or_descendants("ATP:0000079", "ancestors"))
    descendants = set(db.get_ontology_ancestors_or_descendants("ATP:0000079", "descendants"))

    assert {"ATP:0000009", "ATP:0000002", "ATP:0000001"} <= ancestors
    assert {"ATP:0000082", "ATP:0000083", "ATP:0000084"} <= descendants
    assert not ancestors & descendants
    assert "ATP:0000079" not in ancestors | descendants
