"""Data models for AGR Curation API Client."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime, timedelta


class APIConfig(BaseModel):
    """Configuration for AGR Curation API client."""

    base_url: HttpUrl = Field(
        default_factory=lambda: HttpUrl("https://curation.alliancegenome.org/api"),
        description="Base URL for the A-Team Curation API"
    )
    okta_token: Optional[str] = Field(None, description="Okta bearer token for authentication")
    timeout: timedelta = Field(
        default=timedelta(seconds=30),
        description="Request timeout"
    )
    max_retries: int = Field(3, ge=0, description="Maximum number of retry attempts")
    retry_delay: timedelta = Field(
        default=timedelta(seconds=1),
        description="Delay between retry attempts"
    )
    verify_ssl: bool = Field(True, description="Whether to verify SSL certificates")
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional headers to include in requests"
    )

    @field_validator('timeout', 'retry_delay')
    def validate_timedelta(cls, v: timedelta) -> timedelta:
        """Ensure timedelta is positive."""
        if v.total_seconds() <= 0:
            raise ValueError("Timeout and retry_delay must be positive")
        return v

    class Config:
        """Pydantic config."""

        json_encoders = {
            timedelta: lambda v: v.total_seconds()
        }


class AuditedObject(BaseModel):
    """Base class for audited objects with tracking fields."""

    created_by: Optional[Any] = Field(None, alias="createdBy", description="User who created the record")
    date_created: Optional[datetime] = Field(None, alias="dateCreated", description="Date record was created")
    updated_by: Optional[Any] = Field(None, alias="updatedBy", description="User who last updated the record")
    date_updated: Optional[datetime] = Field(None, alias="dateUpdated", description="Date record was last updated")

    @field_validator('created_by', 'updated_by', mode='before')
    def extract_user_id(cls, v):
        """Extract user ID from object if provided as dict."""
        if isinstance(v, dict):
            # Try to extract the uniqueId or id from the user object
            return v.get('uniqueId') or v.get('id') or str(v)
        return v

    class Config:
        populate_by_name = True


class Gene(AuditedObject):
    """Gene model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    primary_external_id: Optional[str] = Field(None, alias="primaryExternalId", description="Primary external ID")
    gene_symbol: Optional[dict] = Field(None, alias="geneSymbol", description="Gene symbol object")
    gene_full_name: Optional[dict] = Field(None, alias="geneFullName", description="Gene full name object")
    gene_systematic_name: Optional[dict] = Field(None, alias="geneSystematicName", description="Gene systematic name")
    gene_synonyms: Optional[List[dict]] = Field(None, alias="geneSynonyms", description="Gene synonyms")
    gene_secondary_ids: Optional[List[dict]] = Field(None, alias="geneSecondaryIds", description="Secondary identifiers")
    gene_type: Optional[dict] = Field(None, alias="geneType", description="SOTerm for gene type")
    data_provider: Optional[dict] = Field(None, alias="dataProvider", description="Data provider")
    taxon: Optional[dict] = Field(None, description="Taxon information")
    obsolete: bool = Field(False, description="Whether gene is obsolete")

    class Config:
        populate_by_name = True


class Species(AuditedObject):
    """Species model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    taxon: Optional[dict] = Field(None, description="NCBITaxonTerm")
    abbreviation: Optional[str] = Field(None, description="Species abbreviation")
    display_name: Optional[str] = Field(None, alias="displayName", description="Display name")
    full_name: Optional[str] = Field(None, alias="fullName", description="Full scientific name")
    genome_assembly: Optional[str] = Field(None, alias="genomeAssembly", description="Current canonical genome assembly")
    common_names: Optional[List[str]] = Field(None, alias="commonNames", description="List of common names")
    phylogenetic_order: Optional[int] = Field(None, alias="phylogeneticOrder", description="Order for species sorting")

    class Config:
        populate_by_name = True


class OntologyTerm(BaseModel):
    """Ontology term model from A-Team curation API."""

    curie: str = Field(..., description="Compact URI")
    name: Optional[str] = Field(None, description="Term name")
    definition: Optional[str] = Field(None, description="Term definition")
    definition_urls: Optional[List[str]] = Field(None, alias="definitionUrls", description="URLs with definitions")
    synonyms: Optional[List[dict]] = Field(None, description="Term synonyms")
    cross_references: Optional[List[dict]] = Field(None, alias="crossReferences", description="External references")
    ancestors: Optional[List[str]] = Field(None, description="Parent terms")
    descendants: Optional[List[str]] = Field(None, description="Child terms")
    child_count: Optional[int] = Field(None, alias="childCount", description="Number of direct children")
    descendant_count: Optional[int] = Field(None, alias="descendantCount", description="Total descendant count")
    obsolete: bool = Field(False, description="Whether term is obsolete")
    namespace: Optional[str] = Field(None, description="Ontology namespace")

    class Config:
        populate_by_name = True


class ExpressionAnnotation(BaseModel):
    """Expression annotation model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    expression_annotation_subject: Optional[dict] = Field(
        None,
        alias="expressionAnnotationSubject",
        description="Expression annotation subject"
    )
    expression_pattern: Optional[dict] = Field(
        None,
        alias="expressionPattern",
        description="Expression pattern"
    )
    when_expressed_stage_name: Optional[str] = Field(
        None,
        alias="whenExpressedStageName",
        description="Human-readable stage name"
    )
    where_expressed_statement: Optional[str] = Field(
        None,
        alias="whereExpressedStatement",
        description="Anatomical expression location"
    )
    single_reference: Optional[dict] = Field(
        None,
        alias="singleReference",
        description="Supporting reference"
    )
    negated: Optional[bool] = Field(None, description="Whether expression is negated")
    uncertain: Optional[bool] = Field(None, description="Whether expression is uncertain")
    expression_qualifiers: Optional[List[str]] = Field(
        None,
        alias="expressionQualifiers",
        description="Expression qualifiers"
    )
    related_notes: Optional[List[dict]] = Field(
        None,
        alias="relatedNotes",
        description="Related notes"
    )

    class Config:
        populate_by_name = True


class Allele(AuditedObject):
    """Allele model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    primary_external_id: Optional[str] = Field(None, alias="primaryExternalId", description="Primary external ID")
    allele_symbol: Optional[dict] = Field(None, alias="alleleSymbol", description="Allele symbol")
    allele_full_name: Optional[dict] = Field(None, alias="alleleFullName", description="Allele full name")
    allele_synonyms: Optional[List[dict]] = Field(None, alias="alleleSynonyms", description="Allele synonyms")
    references: Optional[List[dict]] = Field(None, description="Supporting references")
    laboratory_of_origin: Optional[str] = Field(None, alias="laboratoryOfOrigin", description="Originating laboratory")
    is_extinct: Optional[bool] = Field(None, alias="isExtinct", description="Whether allele is extinct")
    is_extrachromosomal: Optional[bool] = Field(None, alias="isExtrachromosomal", description="Whether allele is extrachromosomal")
    is_integrated: Optional[bool] = Field(None, alias="isIntegrated", description="Whether allele is integrated")
    data_provider: Optional[dict] = Field(None, alias="dataProvider", description="Data provider")
    taxon: Optional[dict] = Field(None, description="Taxon information")
    obsolete: bool = Field(False, description="Whether allele is obsolete")
    gene_associations: Optional[List[dict]] = Field(None, alias="geneAssociations", description="Associated genes")
    protein_associations: Optional[List[dict]] = Field(None, alias="proteinAssociations", description="Associated proteins")
    transcript_associations: Optional[List[dict]] = Field(None, alias="transcriptAssociations", description="Associated transcripts")
    variant_associations: Optional[List[dict]] = Field(None, alias="variantAssociations", description="Associated variants")
    cell_line_associations: Optional[List[dict]] = Field(None, alias="cellLineAssociations", description="Associated cell lines")
    image_associations: Optional[List[dict]] = Field(None, alias="imageAssociations", description="Associated images")
    construct_associations: Optional[List[dict]] = Field(None, alias="constructAssociations", description="Associated constructs")

    class Config:
        populate_by_name = True


class APIResponse(BaseModel):
    """Standard A-Team API response wrapper."""

    total_results: int = Field(..., alias="totalResults", description="Total number of results")
    returned_records: int = Field(..., alias="returnedRecords", description="Number of records returned")
    results: list[Any] = Field(..., description="Result data")

    class Config:
        populate_by_name = True
