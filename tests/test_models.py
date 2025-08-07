#!/usr/bin/env python
"""Unit tests for AGR Curation API models alignment with LinkML schema."""

import unittest
from datetime import datetime
from typing import Set

# Import models directly to avoid initialization issues
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Direct import of models module, bypassing __init__.py to avoid okta initialization issues
import importlib.util
models_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'agr_curation_api', 'models.py')
spec = importlib.util.spec_from_file_location("models", models_path)
models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(models)


class TestModelFieldAlignment(unittest.TestCase):
    """Test that models align with LinkML schema definitions."""
    
    def assertFieldsPresent(self, model_class, expected_fields: Set[str], model_name: str):
        """Helper to assert that expected fields are present in model."""
        actual_fields = set(model_class.model_fields.keys())
        missing_fields = expected_fields - actual_fields
        
        self.assertEqual(
            missing_fields,
            set(),
            f"{model_name} missing fields: {missing_fields}"
        )
    
    def test_audited_object_fields(self):
        """Test AuditedObject has all audit tracking fields."""
        expected_fields = {
            'created_by', 'date_created', 'updated_by', 'date_updated'
        }
        self.assertFieldsPresent(models.AuditedObject, expected_fields, 'AuditedObject')
    
    def test_gene_model_fields(self):
        """Test Gene model has all required LinkML fields."""
        expected_fields = {
            # Core gene fields
            'curie', 'primary_external_id', 'gene_symbol', 'gene_full_name',
            'gene_systematic_name', 'gene_synonyms', 'gene_secondary_ids',
            'gene_type', 'data_provider', 'taxon', 'obsolete',
            # Inherited audit fields
            'created_by', 'date_created', 'updated_by', 'date_updated'
        }
        self.assertFieldsPresent(models.Gene, expected_fields, 'Gene')
    
    def test_species_model_fields(self):
        """Test Species model has all required LinkML fields."""
        expected_fields = {
            # Core species fields
            'curie', 'taxon', 'abbreviation', 'display_name', 'full_name',
            'genome_assembly', 'common_names', 'phylogenetic_order',
            # Inherited audit fields
            'created_by', 'date_created', 'updated_by', 'date_updated'
        }
        self.assertFieldsPresent(models.Species, expected_fields, 'Species')
    
    def test_ontology_term_fields(self):
        """Test OntologyTerm model has all LinkML fields."""
        expected_fields = {
            'curie', 'name', 'definition', 'definition_urls', 'synonyms',
            'cross_references', 'ancestors', 'descendants', 'child_count',
            'descendant_count', 'obsolete', 'namespace'
        }
        self.assertFieldsPresent(models.OntologyTerm, expected_fields, 'OntologyTerm')
    
    def test_expression_annotation_fields(self):
        """Test ExpressionAnnotation model has all LinkML fields."""
        expected_fields = {
            'curie', 'expression_annotation_subject', 'expression_pattern',
            'when_expressed_stage_name', 'where_expressed_statement',
            'single_reference', 'negated', 'uncertain', 
            'expression_qualifiers', 'related_notes'
        }
        self.assertFieldsPresent(models.ExpressionAnnotation, expected_fields, 'ExpressionAnnotation')
    
    def test_allele_model_fields(self):
        """Test Allele model has all LinkML fields."""
        expected_fields = {
            # Core allele fields
            'curie', 'primary_external_id', 'allele_symbol', 'allele_full_name',
            'allele_synonyms', 'references', 'laboratory_of_origin', 'is_extinct',
            'is_extrachromosomal', 'is_integrated', 'data_provider', 'taxon',
            'obsolete',
            # Association fields
            'gene_associations', 'protein_associations', 'transcript_associations',
            'variant_associations', 'cell_line_associations', 'image_associations',
            'construct_associations',
            # Inherited audit fields
            'created_by', 'date_created', 'updated_by', 'date_updated'
        }
        self.assertFieldsPresent(models.Allele, expected_fields, 'Allele')


class TestModelInstantiation(unittest.TestCase):
    """Test that models can be instantiated with valid data."""
    
    def test_audited_object_instantiation(self):
        """Test AuditedObject can be instantiated."""
        audit_obj = models.AuditedObject(
            created_by="test_user",
            date_created=datetime.now(),
            updated_by="test_user",
            date_updated=datetime.now()
        )
        self.assertIsNotNone(audit_obj)
        self.assertEqual(audit_obj.created_by, "test_user")
    
    def test_gene_instantiation(self):
        """Test Gene model instantiation with required fields."""
        gene = models.Gene(
            curie="MGI:12345",
            primary_external_id="MGI:12345",
            gene_symbol={"display_text": "Abc1"},
            gene_type={"curie": "SO:0001217", "name": "protein_coding_gene"},
            taxon={"curie": "NCBITaxon:10090", "name": "Mus musculus"},
            created_by="curator1"
        )
        self.assertIsNotNone(gene)
        self.assertEqual(gene.curie, "MGI:12345")
        self.assertEqual(gene.gene_symbol["display_text"], "Abc1")
    
    def test_species_instantiation(self):
        """Test Species model instantiation."""
        species = models.Species(
            curie="NCBITaxon:10090",
            taxon={"curie": "NCBITaxon:10090", "name": "Mus musculus"},
            abbreviation="Mmu",
            display_name="MOUSE",
            full_name="Mus musculus",
            genome_assembly="GRCm39",
            phylogenetic_order=10
        )
        self.assertIsNotNone(species)
        self.assertEqual(species.abbreviation, "Mmu")
        self.assertEqual(species.genome_assembly, "GRCm39")
    
    def test_ontology_term_instantiation(self):
        """Test OntologyTerm model instantiation."""
        onto_term = models.OntologyTerm(
            curie="GO:0008150",
            name="biological_process",
            definition="Any process specifically pertinent to the functioning of integrated living units",
            namespace="biological_process",
            child_count=29,
            descendant_count=30000
        )
        self.assertIsNotNone(onto_term)
        self.assertEqual(onto_term.curie, "GO:0008150")
        self.assertEqual(onto_term.child_count, 29)
    
    def test_expression_annotation_instantiation(self):
        """Test ExpressionAnnotation model instantiation."""
        expr_annot = models.ExpressionAnnotation(
            curie="EXPR:12345",
            expression_annotation_subject={"curie": "MGI:12345"},
            expression_pattern={"curie": "PATTERN:001"},
            when_expressed_stage_name="embryonic day 10.5",
            where_expressed_statement="dorsal root ganglion",
            single_reference={"curie": "PMID:12345"}
        )
        self.assertIsNotNone(expr_annot)
        self.assertEqual(expr_annot.when_expressed_stage_name, "embryonic day 10.5")
    
    def test_allele_instantiation(self):
        """Test Allele model instantiation."""
        allele = models.Allele(
            curie="MGI:3000001",
            primary_external_id="MGI:3000001",
            allele_symbol={"display_text": "Abc1<tm1Xyz>"},
            references=[{"curie": "PMID:12345"}],
            taxon={"curie": "NCBITaxon:10090"},
            is_extinct=False
        )
        self.assertIsNotNone(allele)
        self.assertEqual(allele.curie, "MGI:3000001")
        self.assertFalse(allele.is_extinct)


class TestModelSerialization(unittest.TestCase):
    """Test model serialization and deserialization."""
    
    def test_gene_json_serialization(self):
        """Test Gene model JSON serialization."""
        gene = models.Gene(
            curie="MGI:12345",
            primary_external_id="MGI:12345",
            gene_symbol={"display_text": "Abc1", "internal": False},
            gene_full_name={"display_text": "ABC transporter 1"},
            gene_type={"curie": "SO:0001217", "name": "protein_coding_gene"},
            gene_secondary_ids=["ENSEMBL:ENSMUSG00000001"],
            taxon={"curie": "NCBITaxon:10090", "name": "Mus musculus"},
            created_by="curator1",
            date_created=datetime.now(),
            obsolete=False
        )
        
        # Test model_dump
        gene_dict = gene.model_dump(by_alias=True, exclude_none=True)
        self.assertIn("primaryExternalId", gene_dict)
        self.assertIn("geneSymbol", gene_dict)
        
        # Test JSON serialization
        gene_json = gene.model_dump_json(by_alias=True, exclude_none=True)
        self.assertIsInstance(gene_json, str)
        
        # Test deserialization
        gene_from_json = models.Gene.model_validate_json(gene_json)
        self.assertEqual(gene_from_json.curie, "MGI:12345")
        self.assertEqual(gene_from_json.primary_external_id, "MGI:12345")
    
    def test_species_json_serialization(self):
        """Test Species model JSON serialization."""
        species = models.Species(
            taxon={"curie": "NCBITaxon:10090"},
            display_name="MOUSE",
            genome_assembly="GRCm39"
        )
        
        species_dict = species.model_dump(by_alias=True, exclude_none=True)
        self.assertIn("displayName", species_dict)
        self.assertIn("genomeAssembly", species_dict)
    
    def test_allele_with_associations(self):
        """Test Allele model with association fields."""
        allele = models.Allele(
            curie="MGI:3000001",
            allele_symbol={"display_text": "Abc1<tm1>"},
            gene_associations=[{"curie": "MGI:12345"}],
            protein_associations=[{"curie": "PROT:001"}],
            is_extinct=False,
            is_extrachromosomal=True
        )
        
        allele_dict = allele.model_dump(by_alias=True, exclude_none=True)
        self.assertIn("geneAssociations", allele_dict)
        self.assertIn("proteinAssociations", allele_dict)
        self.assertIn("isExtinct", allele_dict)
        self.assertIn("isExtrachromosomal", allele_dict)


class TestFieldInheritance(unittest.TestCase):
    """Test that inheritance from AuditedObject works correctly."""
    
    def test_gene_inherits_audit_fields(self):
        """Test Gene inherits audit fields from AuditedObject."""
        gene = models.Gene(
            created_by="curator1",
            date_created=datetime(2024, 1, 1),
            updated_by="curator2",
            date_updated=datetime(2024, 1, 2)
        )
        
        self.assertEqual(gene.created_by, "curator1")
        self.assertEqual(gene.updated_by, "curator2")
        self.assertIsInstance(gene.date_created, datetime)
    
    def test_species_inherits_audit_fields(self):
        """Test Species inherits audit fields from AuditedObject."""
        species = models.Species(
            created_by="admin",
            date_created=datetime.now()
        )
        
        self.assertEqual(species.created_by, "admin")
        self.assertIsNotNone(species.date_created)
    
    def test_allele_inherits_audit_fields(self):
        """Test Allele inherits audit fields from AuditedObject."""
        allele = models.Allele(
            created_by="curator3",
            updated_by="curator4"
        )
        
        self.assertEqual(allele.created_by, "curator3")
        self.assertEqual(allele.updated_by, "curator4")


if __name__ == '__main__':
    unittest.main(verbosity=2)