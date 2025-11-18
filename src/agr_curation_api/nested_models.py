"""
Nested Pydantic models for AGR Curation API.

These models represent the nested objects within the main entities,
converting from generic dictionaries to strongly-typed Pydantic models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# Base Models
class SlotAnnotation(BaseModel):
    """Base class for slot annotations."""

    evidence: Optional[List[str]] = Field(None, description="Supporting evidence")
    internal: Optional[bool] = Field(False, description="Whether annotation is internal")
    obsolete: Optional[bool] = Field(False, description="Whether annotation is obsolete")
    created_by: Optional[str] = Field(None, alias="createdBy")
    date_created: Optional[datetime] = Field(None, alias="dateCreated")
    updated_by: Optional[str] = Field(None, alias="updatedBy")
    date_updated: Optional[datetime] = Field(None, alias="dateUpdated")

    class Config:
        populate_by_name = True


class NameSlotAnnotation(SlotAnnotation):
    """Name-related slot annotation."""

    display_text: str = Field(..., alias="displayText", description="Display text for the name")
    format_text: str = Field(..., alias="formatText", description="Formatted text for the name")
    name_type: Optional[str] = Field(None, alias="nameType", description="Type of name")
    synonym_scope: Optional[str] = Field(None, alias="synonymScope")
    synonym_url: Optional[str] = Field(None, alias="synonymUrl")

    class Config:
        populate_by_name = True


# Taxon/Species Models
class NCBITaxonTerm(BaseModel):
    """NCBI Taxon term."""

    curie: str = Field(..., description="NCBI Taxon ID (e.g., NCBITaxon:9606)")
    name: Optional[str] = Field(None, description="Scientific name")
    common_name: Optional[str] = Field(None, alias="commonName")
    abbreviation: Optional[str] = Field(None)
    internal: Optional[bool] = Field(False)
    obsolete: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True


# Ontology Term Models
class SOTerm(BaseModel):
    """Sequence Ontology term."""

    curie: str = Field(..., description="SO term ID (e.g., SO:0000704)")
    name: Optional[str] = Field(None, description="Term name")
    definition: Optional[str] = Field(None)
    namespace: Optional[str] = Field(None)
    obsolete: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True


class GOTerm(BaseModel):
    """Gene Ontology term."""

    curie: str = Field(..., description="GO term ID (e.g., GO:0008150)")
    name: Optional[str] = Field(None, description="Term name")
    definition: Optional[str] = Field(None)
    namespace: Optional[str] = Field(None)
    obsolete: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True


class VocabularyTerm(BaseModel):
    """Controlled vocabulary term."""

    name: str = Field(..., description="Term name")
    abbreviation: Optional[str] = Field(None)
    definition: Optional[str] = Field(None)
    namespace: Optional[str] = Field(None)
    obsolete: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True


# Cross Reference Models
class CrossReference(BaseModel):
    """Cross reference to external database."""

    referenced_curie: str = Field(..., alias="referencedCurie", description="External database ID")
    display_name: Optional[str] = Field(None, alias="displayName")
    prefix: Optional[str] = Field(None, description="Database prefix")
    page_area: Optional[str] = Field(None, alias="pageArea")
    url: Optional[str] = Field(None)
    internal: Optional[bool] = Field(False)
    obsolete: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True


class DataProvider(BaseModel):
    """Data provider information."""

    source_organization: str = Field(
        ..., alias="sourceOrganization", description="Organization abbreviation (e.g., WB, MGI)"
    )
    cross_reference: Optional[CrossReference] = Field(None, alias="crossReference")

    class Config:
        populate_by_name = True


# Reference Models
class PublicationRef(BaseModel):
    """Reference to a publication."""

    curie: Optional[str] = Field(None, description="Reference ID")
    cross_references: Optional[List[CrossReference]] = Field(None, alias="crossReferences")

    class Config:
        populate_by_name = True


# Gene-specific Models
class GeneSymbolSlotAnnotation(NameSlotAnnotation):
    """Gene symbol annotation."""

    pass


class GeneFullNameSlotAnnotation(NameSlotAnnotation):
    """Gene full name annotation."""

    pass


class GeneSystematicNameSlotAnnotation(NameSlotAnnotation):
    """Gene systematic name annotation."""

    pass


class GeneSynonymSlotAnnotation(NameSlotAnnotation):
    """Gene synonym annotation."""

    pass


class GeneSecondaryIdSlotAnnotation(SlotAnnotation):
    """Gene secondary ID annotation."""

    secondary_id: str = Field(..., alias="secondaryId")

    class Config:
        populate_by_name = True


# Allele-specific Models
class AlleleSymbolSlotAnnotation(NameSlotAnnotation):
    """Allele symbol annotation."""

    pass


class AlleleFullNameSlotAnnotation(NameSlotAnnotation):
    """Allele full name annotation."""

    pass


class AlleleSynonymSlotAnnotation(NameSlotAnnotation):
    """Allele synonym annotation."""

    pass


# Agent/Person Models
class Laboratory(BaseModel):
    """Laboratory information."""

    abbreviation: str = Field(..., description="Lab abbreviation")
    name: Optional[str] = Field(None, description="Full lab name")
    pi_name: Optional[str] = Field(None, alias="piName", description="Principal investigator")
    institution: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


class Person(BaseModel):
    """Person information."""

    unique_id: Optional[str] = Field(None, alias="uniqueId")
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    email: Optional[str] = Field(None)
    orcid: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


# Association Models
class GeneGenomicLocationAssociation(BaseModel):
    """Association between a gene and its genomic location."""

    gene_association_subject: Optional[str] = Field(None, alias="geneAssociationSubject")
    gene_genomic_location_association_object: Optional[str] = Field(None, alias="geneGenomicLocationAssociationObject")
    start: Optional[int] = Field(None, description="Start position")
    end: Optional[int] = Field(None, description="End position")
    strand: Optional[str] = Field(None, description="DNA strand (+/-)")
    chromosome: Optional[str] = Field(None)
    assembly: Optional[str] = Field(None)
    evidence: Optional[List[PublicationRef]] = Field(None)

    class Config:
        populate_by_name = True


class AlleleGeneAssociation(BaseModel):
    """Association between an allele and a gene."""

    allele_association_subject: Optional[str] = Field(None, alias="alleleAssociationSubject")
    allele_gene_association_object: Optional[str] = Field(None, alias="alleleGeneAssociationObject")
    relation: Optional[str] = Field(None, description="Relationship type")
    evidence: Optional[List[PublicationRef]] = Field(None)

    class Config:
        populate_by_name = True


# Note Models
class Note(BaseModel):
    """Note or comment."""

    note_type: Optional[VocabularyTerm] = Field(None, alias="noteType")
    free_text: str = Field(..., alias="freeText", description="Note content")
    evidence: Optional[List[PublicationRef]] = Field(None)
    internal: Optional[bool] = Field(False)

    class Config:
        populate_by_name = True
