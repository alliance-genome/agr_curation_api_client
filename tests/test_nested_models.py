"""Tests for nested Pydantic models."""

import pytest
from pydantic import ValidationError

from agr_curation_api.nested_models import (
    GeneSymbolSlotAnnotation,
    NCBITaxonTerm,
    SOTerm,
    CrossReference,
    DataProvider,
    Laboratory,
    GeneGenomicLocationAssociation,
    Note,
)


class TestGeneSymbolSlotAnnotation:
    """Test GeneSymbolSlotAnnotation model."""

    def test_valid_gene_symbol(self):
        """Test valid gene symbol creation."""
        data = {"displayText": "Pax6", "formatText": "Pax6", "nameType": "nomenclature_symbol"}

        symbol = GeneSymbolSlotAnnotation(**data)
        assert symbol.display_text == "Pax6"
        assert symbol.format_text == "Pax6"
        assert symbol.name_type == "nomenclature_symbol"

    def test_gene_symbol_with_aliases(self):
        """Test gene symbol with field aliases."""
        data = {
            "display_text": "Pax6",  # Using snake_case
            "format_text": "Pax6",
            "createdBy": "user123",
            "dateCreated": "2024-01-15T10:30:00Z",
        }

        symbol = GeneSymbolSlotAnnotation(**data)
        assert symbol.display_text == "Pax6"
        assert symbol.created_by == "user123"

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            GeneSymbolSlotAnnotation()  # Missing required fields


class TestNCBITaxonTerm:
    """Test NCBITaxonTerm model."""

    def test_valid_taxon(self):
        """Test valid taxon creation."""
        data = {"curie": "NCBITaxon:9606", "name": "Homo sapiens", "common_name": "human", "abbreviation": "Hsa"}

        taxon = NCBITaxonTerm(**data)
        assert taxon.curie == "NCBITaxon:9606"
        assert taxon.name == "Homo sapiens"
        assert taxon.common_name == "human"

    def test_curie_required(self):
        """Test that curie is required."""
        with pytest.raises(ValidationError):
            NCBITaxonTerm(name="Homo sapiens")


class TestSOTerm:
    """Test SOTerm model."""

    def test_valid_so_term(self):
        """Test valid SO term creation."""
        data = {
            "curie": "SO:0000704",
            "name": "gene",
            "definition": "A region (or regions) that includes all of the sequence elements necessary to encode a functional transcript.",
        }

        so_term = SOTerm(**data)
        assert so_term.curie == "SO:0000704"
        assert so_term.name == "gene"
        assert "sequence elements" in so_term.definition


class TestCrossReference:
    """Test CrossReference model."""

    def test_valid_cross_reference(self):
        """Test valid cross reference creation."""
        data = {
            "referencedCurie": "UniProtKB:P63330",
            "displayName": "Pax6 protein",
            "prefix": "UniProtKB",
            "pageArea": "gene",
        }

        cross_ref = CrossReference(**data)
        assert cross_ref.referenced_curie == "UniProtKB:P63330"
        assert cross_ref.display_name == "Pax6 protein"
        assert cross_ref.prefix == "UniProtKB"

    def test_referenced_curie_required(self):
        """Test that referenced_curie is required."""
        with pytest.raises(ValidationError):
            CrossReference(display_name="Some protein")


class TestDataProvider:
    """Test DataProvider model."""

    def test_valid_data_provider(self):
        """Test valid data provider creation."""
        cross_ref_data = {"referencedCurie": "WB:WBGene00000001", "displayName": "Gene Page"}

        data = {"sourceOrganization": "WB", "crossReference": cross_ref_data}

        provider = DataProvider(**data)
        assert provider.source_organization == "WB"
        assert provider.cross_reference.referenced_curie == "WB:WBGene00000001"

    def test_source_organization_required(self):
        """Test that source_organization is required."""
        with pytest.raises(ValidationError):
            DataProvider()


class TestLaboratory:
    """Test Laboratory model."""

    def test_valid_laboratory(self):
        """Test valid laboratory creation."""
        data = {
            "abbreviation": "Horvitz Lab",
            "name": "Robert Horvitz Laboratory",
            "piName": "H. Robert Horvitz",
            "institution": "MIT",
        }

        lab = Laboratory(**data)
        assert lab.abbreviation == "Horvitz Lab"
        assert lab.pi_name == "H. Robert Horvitz"
        assert lab.institution == "MIT"


class TestGeneGenomicLocationAssociation:
    """Test GeneGenomicLocationAssociation model."""

    def test_valid_location_association(self):
        """Test valid location association creation."""
        data = {
            "geneAssociationSubject": "WB:WBGene00000001",
            "start": 1000000,
            "end": 1005000,
            "strand": "+",
            "chromosome": "I",
            "assembly": "WBcel235",
        }

        location = GeneGenomicLocationAssociation(**data)
        assert location.start == 1000000
        assert location.end == 1005000
        assert location.strand == "+"
        assert location.chromosome == "I"


class TestNote:
    """Test Note model."""

    def test_valid_note(self):
        """Test valid note creation."""
        note_type_data = {"name": "automated_description", "definition": "Automated gene description"}

        data = {"noteType": note_type_data, "freeText": "This gene encodes a transcription factor.", "internal": False}

        note = Note(**data)
        assert note.free_text == "This gene encodes a transcription factor."
        assert note.note_type.name == "automated_description"
        assert note.internal is False

    def test_free_text_required(self):
        """Test that freeText is required."""
        with pytest.raises(ValidationError):
            Note(noteType={"name": "test"})


class TestModelIntegration:
    """Test integration between different models."""

    def test_nested_model_parsing(self):
        """Test that models can be nested properly."""
        # Create a complex nested structure
        taxon_data = {"curie": "NCBITaxon:6239", "name": "Caenorhabditis elegans", "abbreviation": "Cel"}

        gene_type_data = {"curie": "SO:0000704", "name": "gene"}

        symbol_data = {"displayText": "unc-18", "formatText": "unc-18"}

        # Test that these can be created independently
        taxon = NCBITaxonTerm(**taxon_data)
        gene_type = SOTerm(**gene_type_data)
        symbol = GeneSymbolSlotAnnotation(**symbol_data)

        # Verify they have expected attributes
        assert taxon.name == "Caenorhabditis elegans"
        assert gene_type.name == "gene"
        assert symbol.display_text == "unc-18"

    def test_dict_to_model_conversion(self):
        """Test conversion from dict to model objects."""
        # This simulates what happens in the field validators
        dict_data = {"curie": "NCBITaxon:9606", "name": "Homo sapiens"}

        # Direct model creation
        taxon = NCBITaxonTerm(**dict_data)
        assert taxon.curie == "NCBITaxon:9606"
        assert taxon.name == "Homo sapiens"

        # Test that validation works
        assert isinstance(taxon, NCBITaxonTerm)

    def test_optional_fields(self):
        """Test that optional fields work correctly."""
        # Minimal data
        minimal_taxon = NCBITaxonTerm(curie="NCBITaxon:9606")
        assert minimal_taxon.curie == "NCBITaxon:9606"
        assert minimal_taxon.name is None
        assert minimal_taxon.common_name is None

        # With optional fields
        full_taxon = NCBITaxonTerm(curie="NCBITaxon:9606", name="Homo sapiens", common_name="human")
        assert full_taxon.name == "Homo sapiens"
        assert full_taxon.common_name == "human"
