from __future__ import annotations

import re
import sys
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


metamodel_version = "None"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        use_enum_values=True,
        strict=False,
    )
    pass


class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key: str):
        return getattr(self.root, key)

    def __getitem__(self, key: str):
        return self.root[key]

    def __setitem__(self, key: str, value):
        self.root[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta(
    {
        "default_prefix": "alliance",
        "default_range": "string",
        "description": "Targeted minimal schema for AGR API client",
        "id": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml",
        "imports": ["linkml:types"],
        "name": "targeted_agr_schema",
        "prefixes": {
            "NCBITaxon": {
                "prefix_prefix": "NCBITaxon",
                "prefix_reference": "http://purl.obolibrary.org/obo/NCBITaxon_",
            },
            "SO": {"prefix_prefix": "SO", "prefix_reference": "http://purl.obolibrary.org/obo/SO_"},
            "alliance": {"prefix_prefix": "alliance", "prefix_reference": "http://alliancegenome.org/"},
            "linkml": {"prefix_prefix": "linkml", "prefix_reference": "https://w3id.org/linkml/"},
        },
        "source_file": "/tmp/tmpwrqvbais.yaml",
    }
)


class CrossReference(ConfiguredBaseModel):
    """
    Cross reference to external database
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayName: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "displayName", "domain_of": ["CrossReference"]}}
    )
    pageArea: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "pageArea", "domain_of": ["CrossReference"]}}
    )
    prefix: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "prefix", "domain_of": ["CrossReference"]}}
    )
    referencedCurie: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "referencedCurie", "domain_of": ["CrossReference"]}}
    )
    url: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "url", "domain_of": ["CrossReference"]}}
    )


class DataProvider(ConfiguredBaseModel):
    """
    Data provider information
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    crossReference: Optional[CrossReference] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "crossReference", "domain_of": ["DataProvider"]}}
    )
    sourceOrganization: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "sourceOrganization", "domain_of": ["DataProvider"]}}
    )


class Laboratory(ConfiguredBaseModel):
    """
    Laboratory information
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    abbreviation: str = Field(
        default=...,
        json_schema_extra={"linkml_meta": {"alias": "abbreviation", "domain_of": ["Laboratory", "NCBITaxonTerm"]}},
    )
    institution: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "institution", "domain_of": ["Laboratory"]}}
    )
    name: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "name", "domain_of": ["Laboratory", "OntologyTerm"]}}
    )
    piName: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "piName", "domain_of": ["Laboratory"]}}
    )


class Note(ConfiguredBaseModel):
    """
    Note or comment
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    freeText: str = Field(default=..., json_schema_extra={"linkml_meta": {"alias": "freeText", "domain_of": ["Note"]}})
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )


class OntologyTerm(ConfiguredBaseModel):
    """
    Base ontology term
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    curie: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "curie", "domain_of": ["OntologyTerm"]}}
    )
    definition: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "definition", "domain_of": ["OntologyTerm"]}}
    )
    name: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "name", "domain_of": ["Laboratory", "OntologyTerm"]}}
    )
    namespace: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "namespace", "domain_of": ["OntologyTerm"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class NCBITaxonTerm(OntologyTerm):
    """
    NCBI Taxon term
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    abbreviation: Optional[str] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "abbreviation", "domain_of": ["Laboratory", "NCBITaxonTerm"]}},
    )
    commonName: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "commonName", "domain_of": ["NCBITaxonTerm"]}}
    )
    curie: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "curie", "domain_of": ["OntologyTerm"]}}
    )
    definition: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "definition", "domain_of": ["OntologyTerm"]}}
    )
    name: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "name", "domain_of": ["Laboratory", "OntologyTerm"]}}
    )
    namespace: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "namespace", "domain_of": ["OntologyTerm"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class SOTerm(OntologyTerm):
    """
    Sequence Ontology term
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    curie: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "curie", "domain_of": ["OntologyTerm"]}}
    )
    definition: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "definition", "domain_of": ["OntologyTerm"]}}
    )
    name: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "name", "domain_of": ["Laboratory", "OntologyTerm"]}}
    )
    namespace: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "namespace", "domain_of": ["OntologyTerm"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class SlotAnnotation(ConfiguredBaseModel):
    """
    Base class for slot annotations with evidence
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class NameSlotAnnotation(SlotAnnotation):
    """
    Name/symbol annotation with display text
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class AlleleFullNameSlotAnnotation(NameSlotAnnotation):
    """
    Allele full name annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class AlleleSymbolSlotAnnotation(NameSlotAnnotation):
    """
    Allele symbol annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class AlleleSynonymSlotAnnotation(NameSlotAnnotation):
    """
    Allele synonym annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class GeneFullNameSlotAnnotation(NameSlotAnnotation):
    """
    Gene full name annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class GeneSymbolSlotAnnotation(NameSlotAnnotation):
    """
    Gene symbol annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class GeneSynonymSlotAnnotation(NameSlotAnnotation):
    """
    Gene synonym annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


class GeneSystematicNameSlotAnnotation(NameSlotAnnotation):
    """
    Gene systematic name annotation
    """

    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta(
        {"from_schema": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml"}
    )

    displayText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "displayText", "domain_of": ["NameSlotAnnotation"]}}
    )
    formatText: str = Field(
        default=..., json_schema_extra={"linkml_meta": {"alias": "formatText", "domain_of": ["NameSlotAnnotation"]}}
    )
    nameType: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "nameType", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymScope: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymScope", "domain_of": ["NameSlotAnnotation"]}}
    )
    synonymUrl: Optional[str] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "synonymUrl", "domain_of": ["NameSlotAnnotation"]}}
    )
    evidence: Optional[list[str]] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "evidence", "domain_of": ["SlotAnnotation"]}}
    )
    internal: Optional[bool] = Field(
        default=None, json_schema_extra={"linkml_meta": {"alias": "internal", "domain_of": ["Note", "SlotAnnotation"]}}
    )
    obsolete: Optional[bool] = Field(
        default=None,
        json_schema_extra={"linkml_meta": {"alias": "obsolete", "domain_of": ["OntologyTerm", "SlotAnnotation"]}},
    )


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
CrossReference.model_rebuild()
DataProvider.model_rebuild()
Laboratory.model_rebuild()
Note.model_rebuild()
OntologyTerm.model_rebuild()
NCBITaxonTerm.model_rebuild()
SOTerm.model_rebuild()
SlotAnnotation.model_rebuild()
NameSlotAnnotation.model_rebuild()
AlleleFullNameSlotAnnotation.model_rebuild()
AlleleSymbolSlotAnnotation.model_rebuild()
AlleleSynonymSlotAnnotation.model_rebuild()
GeneFullNameSlotAnnotation.model_rebuild()
GeneSymbolSlotAnnotation.model_rebuild()
GeneSynonymSlotAnnotation.model_rebuild()
GeneSystematicNameSlotAnnotation.model_rebuild()

