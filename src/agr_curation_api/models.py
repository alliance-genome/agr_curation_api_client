"""Data models for AGR Curation API Client."""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import timedelta


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


class Gene(BaseModel):
    """Gene model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    primary_external_id: Optional[str] = Field(None, alias="primaryExternalId", description="Primary external ID")
    gene_symbol: Optional[dict] = Field(None, alias="geneSymbol", description="Gene symbol object")
    gene_full_name: Optional[dict] = Field(None, alias="geneFullName", description="Gene full name object")
    gene_systematic_name: Optional[dict] = Field(None, alias="geneSystematicName", description="Gene systematic name")
    gene_synonyms: Optional[list[dict]] = Field(None, alias="geneSynonyms", description="Gene synonyms")
    data_provider: Optional[dict] = Field(None, alias="dataProvider", description="Data provider")
    taxon: Optional[dict] = Field(None, description="Taxon information")
    obsolete: bool = Field(False, description="Whether gene is obsolete")

    class Config:
        populate_by_name = True


class Species(BaseModel):
    """Species model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    abbreviation: str = Field(..., description="Species abbreviation")
    display_name: Optional[str] = Field(None, alias="displayName", description="Display name")
    full_name: Optional[str] = Field(None, alias="fullName", description="Full scientific name")

    class Config:
        populate_by_name = True


class OntologyTerm(BaseModel):
    """Ontology term model from A-Team curation API."""

    curie: str = Field(..., description="Compact URI")
    name: Optional[str] = Field(None, description="Term name")
    definition: Optional[str] = Field(None, description="Term definition")
    synonyms: Optional[list[dict]] = Field(None, description="Term synonyms")
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

    class Config:
        populate_by_name = True


class Allele(BaseModel):
    """Allele model from A-Team curation API."""

    curie: Optional[str] = Field(None, description="Compact URI")
    primary_external_id: Optional[str] = Field(None, alias="primaryExternalId", description="Primary external ID")
    allele_symbol: Optional[dict] = Field(None, alias="alleleSymbol", description="Allele symbol")
    allele_full_name: Optional[dict] = Field(None, alias="alleleFullName", description="Allele full name")
    allele_synonyms: Optional[list[dict]] = Field(None, alias="alleleSynonyms", description="Allele synonyms")
    data_provider: Optional[dict] = Field(None, alias="dataProvider", description="Data provider")
    taxon: Optional[dict] = Field(None, description="Taxon information")
    obsolete: bool = Field(False, description="Whether allele is obsolete")

    class Config:
        populate_by_name = True


class APIResponse(BaseModel):
    """Standard A-Team API response wrapper."""

    total_results: int = Field(..., alias="totalResults", description="Total number of results")
    returned_records: int = Field(..., alias="returnedRecords", description="Number of records returned")
    results: list[Any] = Field(..., description="Result data")

    class Config:
        populate_by_name = True
