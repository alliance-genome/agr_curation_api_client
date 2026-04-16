#!/usr/bin/env python
"""Unit tests for API methods: ObjectResponse unwrapping and get_or_create_species."""

import unittest
from unittest.mock import MagicMock

from agr_curation_api.api_methods import APIMethods
from agr_curation_api.models import NCBITaxonTerm
from agr_curation_api.exceptions import AGRAPIError


class TestObjectResponseUnwrapping(unittest.TestCase):
    """Test that get-by-id methods properly unwrap ObjectResponse wrappers."""

    def setUp(self):
        self.mock_request = MagicMock()
        self.api = APIMethods(self.mock_request)

    def test_get_gene_unwraps_entity(self):
        """get_gene should extract entity from ObjectResponse wrapper."""
        self.mock_request.return_value = {
            "entity": {
                "primaryExternalId": "WB:WBGene00000001",
                "curie": "WB:WBGene00000001",
                "geneSymbol": {"displayText": "aap-1"},
                "obsolete": False,
            }
        }
        gene = self.api.get_gene("WB:WBGene00000001")
        self.assertEqual(gene.curie, "WB:WBGene00000001")
        self.assertEqual(gene.geneSymbol.displayText, "aap-1")

    def test_get_gene_handles_unwrapped_response(self):
        """get_gene should still work if response is not wrapped."""
        self.mock_request.return_value = {
            "primaryExternalId": "WB:WBGene00000001",
            "curie": "WB:WBGene00000001",
            "geneSymbol": {"displayText": "aap-1"},
            "obsolete": False,
        }
        gene = self.api.get_gene("WB:WBGene00000001")
        self.assertEqual(gene.curie, "WB:WBGene00000001")

    def test_get_gene_returns_none_on_error(self):
        """get_gene should return None when the request fails."""
        self.mock_request.side_effect = Exception("Not found")
        gene = self.api.get_gene("INVALID:ID")
        self.assertIsNone(gene)

    def test_get_ncbi_taxon_term_unwraps_entity(self):
        """get_ncbi_taxon_term should extract entity from ObjectResponse wrapper."""
        self.mock_request.return_value = {
            "entity": {
                "curie": "NCBITaxon:6239",
                "name": "Caenorhabditis elegans",
                "obsolete": False,
            }
        }
        term = self.api.get_ncbi_taxon_term("NCBITaxon:6239")
        self.assertEqual(term.curie, "NCBITaxon:6239")
        self.assertEqual(term.name, "Caenorhabditis elegans")

    def test_get_ncbi_taxon_term_returns_none_on_error(self):
        """get_ncbi_taxon_term should return None when the request fails."""
        self.mock_request.side_effect = Exception("Not found")
        term = self.api.get_ncbi_taxon_term("NCBITaxon:9999999")
        self.assertIsNone(term)

    def test_get_allele_unwraps_entity(self):
        """get_allele should extract entity from ObjectResponse wrapper."""
        self.mock_request.return_value = {
            "entity": {
                "primaryExternalId": "MGI:5249690",
                "curie": "MGI:5249690",
                "alleleSymbol": {"displayText": "Gt(IST14665F12)Tigm"},
                "obsolete": False,
            }
        }
        allele = self.api.get_allele("MGI:5249690")
        self.assertEqual(allele.curie, "MGI:5249690")
        self.assertEqual(allele.alleleSymbol.displayText, "Gt(IST14665F12)Tigm")

    def test_get_agm_unwraps_entity(self):
        """get_agm should extract entity from ObjectResponse wrapper."""
        self.mock_request.return_value = {
            "entity": {
                "curie": "ZFIN:ZDB-FISH-150901-1",
                "modEntityId": "ZFIN:ZDB-FISH-150901-1",
                "obsolete": False,
            }
        }
        agm = self.api.get_agm("ZFIN:ZDB-FISH-150901-1")
        self.assertEqual(agm.curie, "ZFIN:ZDB-FISH-150901-1")


class TestGetOrCreateSpecies(unittest.TestCase):
    """Test get_or_create_species method."""

    def setUp(self):
        self.mock_request = MagicMock()
        self.api = APIMethods(self.mock_request)

    def test_numeric_taxon_id_is_normalized(self):
        """Numeric taxon ID should be prefixed with NCBITaxon:."""
        self.mock_request.return_value = {
            "entity": {
                "curie": "NCBITaxon:6239",
                "name": "Caenorhabditis elegans",
            }
        }
        self.api.get_or_create_species("6239")
        self.mock_request.assert_called_once_with("GET", "ncbitaxonterm/NCBITaxon:6239")

    def test_full_curie_is_passed_as_is(self):
        """Full CURIE should not be double-prefixed."""
        self.mock_request.return_value = {
            "entity": {
                "curie": "NCBITaxon:9606",
                "name": "Homo sapiens",
            }
        }
        self.api.get_or_create_species("NCBITaxon:9606")
        self.mock_request.assert_called_once_with("GET", "ncbitaxonterm/NCBITaxon:9606")

    def test_returns_ncbi_taxon_term(self):
        """Should return a properly parsed NCBITaxonTerm."""
        self.mock_request.return_value = {
            "entity": {
                "curie": "NCBITaxon:6239",
                "name": "Caenorhabditis elegans",
                "namespace": "ncbi_taxonomy",
                "obsolete": False,
            }
        }
        result = self.api.get_or_create_species("6239")
        self.assertIsInstance(result, NCBITaxonTerm)
        self.assertEqual(result.curie, "NCBITaxon:6239")
        self.assertEqual(result.name, "Caenorhabditis elegans")

    def test_raises_on_error_message(self):
        """Should raise AGRAPIError when response contains errorMessage."""
        self.mock_request.return_value = {
            "entity": None,
            "errorMessage": "Invalid taxon ID",
        }
        with self.assertRaises(AGRAPIError) as ctx:
            self.api.get_or_create_species("invalid")
        self.assertIn("Invalid taxon ID", str(ctx.exception))

    def test_raises_on_error_messages_dict(self):
        """Should raise AGRAPIError when response contains errorMessages dict."""
        self.mock_request.return_value = {
            "entity": None,
            "errorMessages": {"curie": "Not a valid NCBI taxon"},
        }
        with self.assertRaises(AGRAPIError) as ctx:
            self.api.get_or_create_species("bad_id")
        self.assertIn("Not a valid NCBI taxon", str(ctx.exception))

    def test_raises_on_missing_entity(self):
        """Should raise AGRAPIError when response has no entity."""
        self.mock_request.return_value = {}
        with self.assertRaises(AGRAPIError) as ctx:
            self.api.get_or_create_species("6239")
        self.assertIn("no entity in response", str(ctx.exception))

    def test_raises_on_request_failure(self):
        """Should propagate request exceptions."""
        self.mock_request.side_effect = AGRAPIError("Connection failed")
        with self.assertRaises(AGRAPIError):
            self.api.get_or_create_species("6239")


if __name__ == "__main__":
    unittest.main()
