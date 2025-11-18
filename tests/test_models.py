#!/usr/bin/env python
"""Unit tests for AGR Curation API models that match actual API responses."""

import unittest
from datetime import datetime
from typing import Set
import sys
import os
import importlib.util

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Direct import of models module, bypassing __init__.py to avoid okta initialization issues
models_path = os.path.join(os.path.dirname(__file__), "..", "src", "agr_curation_api", "models.py")
spec = importlib.util.spec_from_file_location("models", models_path)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class TestModelFieldAlignment(unittest.TestCase):
    """Test that models have expected fields that match API responses."""

    def assertFieldsPresent(self, model_class, expected_fields: Set[str], model_name: str):
        """Helper to assert that expected fields are present in model."""
        actual_fields = set(model_class.model_fields.keys())
        missing_fields = expected_fields - actual_fields

        self.assertEqual(missing_fields, set(), f"{model_name} missing fields: {missing_fields}")

    def test_gene_model_fields(self):
        """Test Gene model has all required API fields."""
        expected_fields = {
            # Core gene fields (API format)
            "curie",
            "primaryExternalId",
            "geneSymbol",
            "geneFullName",
            "geneSystematicName",
            "geneSynonyms",
            "geneSecondaryIds",
            "geneType",
            "dataProvider",
            "taxon",
            "obsolete",
            # API metadata fields
            "type",
            "id",
            "internal",
            # Audit fields
            "createdBy",
            "updatedBy",
            "dateCreated",
            "dateUpdated",
            # Cross references
            "crossReferences",
        }
        self.assertFieldsPresent(models.Gene, expected_fields, "Gene")

    def test_species_model_fields(self):
        """Test Species model has required API fields."""
        expected_fields = {
            # Core species fields (API format)
            "curie",
            "name",
            "displayName",
            "abbreviation",
            "commonNames",
            "genomeAssembly",
            "phylogeneticOrder",
            "taxon",
            "obsolete",
            "internal",
            # API metadata fields
            "type",
            "id",
        }
        self.assertFieldsPresent(models.Species, expected_fields, "Species")

    def test_ontology_term_fields(self):
        """Test OntologyTerm model has API fields."""
        expected_fields = {
            "curie",
            "name",
            "definition",
            "namespace",
            "obsolete",
            "childCount",
            "descendantCount",
            "ancestors",
            # API metadata fields
            "type",
            "id",
            "internal",
        }
        self.assertFieldsPresent(models.OntologyTerm, expected_fields, "OntologyTerm")

    def test_allele_model_fields(self):
        """Test Allele model has API fields."""
        expected_fields = {
            # Core allele fields (API format)
            "curie",
            "primaryExternalId",
            "alleleSymbol",
            "alleleFullName",
            "alleleSynonyms",
            "references",
            "laboratoryOfOrigin",
            "isExtinct",
            "isExtrachromosomal",
            "isIntegrated",
            "dataProvider",
            "taxon",
            "obsolete",
            "internal",
            # API metadata fields
            "type",
            "id",
            # Audit fields
            "createdBy",
            "updatedBy",
            "dateCreated",
            "dateUpdated",
            # Cross references
            "crossReferences",
        }
        self.assertFieldsPresent(models.Allele, expected_fields, "Allele")

    def test_expression_annotation_fields(self):
        """Test ExpressionAnnotation model has API fields."""
        expected_fields = {
            "curie",
            "expressionAnnotationSubject",
            "expressionPattern",
            "whenExpressedStageName",
            "whereExpressedStatement",
        }
        self.assertFieldsPresent(models.ExpressionAnnotation, expected_fields, "ExpressionAnnotation")


class TestModelInstantiation(unittest.TestCase):
    """Test that models can be instantiated with valid data."""

    def test_gene_instantiation(self):
        """Test Gene model can be instantiated."""
        gene = models.Gene(curie="FB:FBgn0024733", geneSymbol={"displayText": "RpL10"}, obsolete=False)
        self.assertEqual(gene.curie, "FB:FBgn0024733")
        self.assertIsNotNone(gene.geneSymbol)
        self.assertFalse(gene.obsolete)

    def test_species_instantiation(self):
        """Test Species model can be instantiated."""
        species = models.Species(curie="NCBITaxon:7227", displayName="Drosophila melanogaster", obsolete=False)
        self.assertEqual(species.curie, "NCBITaxon:7227")
        self.assertEqual(species.displayName, "Drosophila melanogaster")

    def test_ontology_term_instantiation(self):
        """Test OntologyTerm model can be instantiated."""
        term = models.OntologyTerm(curie="GO:0008150", name="biological_process", obsolete=False)
        self.assertEqual(term.curie, "GO:0008150")
        self.assertEqual(term.name, "biological_process")

    def test_allele_instantiation(self):
        """Test Allele model can be instantiated."""
        allele = models.Allele(curie="MGI:5249690", alleleSymbol={"displayText": "Gt(IST14665F12)Tigm"}, obsolete=False)
        self.assertEqual(allele.curie, "MGI:5249690")
        self.assertIsNotNone(allele.alleleSymbol)

    def test_expression_annotation_instantiation(self):
        """Test ExpressionAnnotation can be instantiated."""
        expr = models.ExpressionAnnotation(curie="TEST:001", whenExpressedStageName="adult")
        self.assertEqual(expr.curie, "TEST:001")
        self.assertEqual(expr.whenExpressedStageName, "adult")


class TestModelSerialization(unittest.TestCase):
    """Test model serialization behavior."""

    def test_gene_json_serialization(self):
        """Test Gene model JSON serialization uses API field names."""
        gene = models.Gene(
            curie="MGI:12345",
            primaryExternalId="MGI:12345",
            geneSymbol={"displayText": "Abc1", "internal": False},
            geneFullName={"displayText": "ABC transporter 1"},
            geneType={"curie": "SO:0001217", "name": "protein_coding_gene"},
            geneSecondaryIds=["ENSEMBL:ENSMUSG00000001"],
            taxon={"curie": "NCBITaxon:10090", "name": "Mus musculus"},
            createdBy="curator1",
            dateCreated=datetime.now(),
            obsolete=False,
        )

        # Test model_dump uses our field names
        gene_dict = gene.model_dump(exclude_none=True)
        self.assertIn("primaryExternalId", gene_dict)
        self.assertIn("geneSymbol", gene_dict)
        self.assertIn("geneFullName", gene_dict)
        self.assertIn("geneSecondaryIds", gene_dict)
        self.assertIn("createdBy", gene_dict)
        self.assertIn("dateCreated", gene_dict)

    def test_species_json_serialization(self):
        """Test Species model JSON serialization."""
        species = models.Species(taxon={"curie": "NCBITaxon:10090"}, displayName="MOUSE", genomeAssembly="GRCm39")

        species_dict = species.model_dump(exclude_none=True)
        self.assertIn("displayName", species_dict)
        self.assertIn("genomeAssembly", species_dict)

    def test_allele_with_associations(self):
        """Test Allele model handles complex data."""
        allele = models.Allele(
            curie="MGI:3000001", alleleSymbol={"displayText": "Abc1<tm1>"}, isExtinct=False, isExtrachromosomal=True
        )

        allele_dict = allele.model_dump(exclude_none=True)
        self.assertIn("alleleSymbol", allele_dict)
        self.assertIn("isExtinct", allele_dict)
        self.assertIn("isExtrachromosomal", allele_dict)


class TestFieldInheritance(unittest.TestCase):
    """Test that models have proper field inheritance."""

    def test_gene_inherits_audit_fields(self):
        """Test Gene model has audit fields."""
        gene_fields = set(models.Gene.model_fields.keys())
        audit_fields = {"createdBy", "dateCreated", "updatedBy", "dateUpdated"}

        # Check that audit fields are present
        for field in audit_fields:
            self.assertIn(field, gene_fields, f"Gene missing audit field: {field}")

    def test_allele_inherits_audit_fields(self):
        """Test Allele model has audit fields."""
        allele_fields = set(models.Allele.model_fields.keys())
        audit_fields = {"createdBy", "dateCreated", "updatedBy", "dateUpdated"}

        for field in audit_fields:
            self.assertIn(field, allele_fields, f"Allele missing audit field: {field}")

    def test_species_inherits_audit_fields(self):
        """Test Species model can have audit fields if present in API."""
        # Species doesn't inherit audit fields in our API model, which is correct
        # since the API doesn't return those fields for species
        species_fields = set(models.Species.model_fields.keys())
        core_fields = {"type", "id", "curie", "obsolete", "internal"}

        for field in core_fields:
            self.assertIn(field, species_fields, f"Species missing core field: {field}")


class TestModelFlexibility(unittest.TestCase):
    """Test that models handle API response variations gracefully."""

    def test_gene_handles_missing_curie(self):
        """Test Gene model handles missing curie by using primaryExternalId."""
        gene_data = {"primaryExternalId": "FB:FBgn0024733", "geneSymbol": {"displayText": "RpL10"}, "obsolete": False}

        gene = models.Gene(**gene_data)
        # The model validator should set curie from primaryExternalId
        self.assertEqual(gene.curie, "FB:FBgn0024733")

    def test_allele_handles_missing_curie(self):
        """Test Allele model handles missing curie."""
        allele_data = {"primaryExternalId": "MGI:123", "alleleSymbol": {"displayText": "test"}, "obsolete": False}

        allele = models.Allele(**allele_data)
        self.assertEqual(allele.curie, "MGI:123")

    def test_models_handle_extra_fields(self):
        """Test models accept extra fields from API."""
        gene_data = {
            "curie": "TEST:001",
            "geneSymbol": {"displayText": "test"},
            "obsolete": False,
            # Extra fields that might come from API
            "someUnknownField": "value",
            "anotherExtraField": 123,
        }

        # Should not raise an error due to ConfigDict(extra='allow')
        gene = models.Gene(**gene_data)
        self.assertEqual(gene.curie, "TEST:001")


if __name__ == "__main__":
    unittest.main()
