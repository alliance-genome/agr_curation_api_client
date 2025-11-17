"""GraphQL query builder utilities for AGR Curation API."""

from typing import List, Dict, Optional, Set, Union, Any


class FieldSelector:
    """Helper class to manage field selection for GraphQL queries."""

    # Default fields for genes - minimal set that's always useful
    DEFAULT_GENE_FIELDS = {"primaryExternalId", "curie", "obsolete", "internal"}

    # All available gene fields organized by category
    ALL_GENE_FIELDS = {
        # Basic fields
        "id",
        "primaryExternalId",
        "curie",
        "obsolete",
        "internal",
        # Audit fields
        "dateCreated",
        "dateUpdated",
        "dbDateCreated",
        "dbDateUpdated",
    }

    # Nested object fields that require sub-selection
    GENE_NESTED_FIELDS = {
        "createdBy": ["id", "uniqueId"],
        "updatedBy": ["id", "uniqueId"],
        "geneSymbol": ["displayText", "formatText"],
        "geneFullName": ["displayText", "formatText"],
        "geneSystematicName": ["displayText", "formatText"],
        "geneSynonyms": ["displayText", "formatText"],
        "geneSecondaryIds": ["secondaryId"],
        "geneType": ["name", "curie"],
        "dataProvider": ["abbreviation", "fullName"],
        "taxon": ["curie", "name"],
        "crossReferences": ["referencedCurie", "displayName", "prefix"],
    }

    # Preset field groups for common use cases
    GENE_FIELD_PRESETS = {
        "minimal": ["primaryExternalId", "curie", "geneSymbol", "obsolete"],
        "basic": ["primaryExternalId", "curie", "geneSymbol", "geneFullName", "taxon", "obsolete"],
        "standard": [
            "id",
            "primaryExternalId",
            "curie",
            "geneSymbol",
            "geneFullName",
            "geneSystematicName",
            "geneSynonyms",
            "geneType",
            "taxon",
            "dataProvider",
            "obsolete",
            "internal",
        ],
        "full": [
            "id",
            "primaryExternalId",
            "curie",
            "createdBy",
            "updatedBy",
            "dateCreated",
            "dateUpdated",
            "dbDateCreated",
            "dbDateUpdated",
            "geneSymbol",
            "geneFullName",
            "geneSystematicName",
            "geneSynonyms",
            "geneSecondaryIds",
            "geneType",
            "taxon",
            "dataProvider",
            "crossReferences",
            "obsolete",
            "internal",
        ],
    }

    @classmethod
    def expand_fields(cls, fields: Union[str, List[str], None]) -> Set[str]:
        """Expand field specification into a set of field names.

        Args:
            fields: Can be:
                - None: use "standard" preset
                - "minimal", "basic", "standard", "full": use preset
                - List of field names: use exactly those fields
                - Single field name string: use that field + defaults

        Returns:
            Set of field names to include in query
        """
        if fields is None:
            fields = "standard"

        if isinstance(fields, str):
            # Check if it's a preset
            if fields in cls.GENE_FIELD_PRESETS:
                return set(cls.GENE_FIELD_PRESETS[fields])
            # Otherwise treat as single field name
            result = cls.DEFAULT_GENE_FIELDS.copy()
            result.add(fields)
            return result

        # It's a list of field names
        return set(fields)

    @classmethod
    def build_field_selection(cls, fields: Set[str], indent: int = 2) -> str:
        """Build GraphQL field selection string from field set.

        Args:
            fields: Set of field names to include
            indent: Number of spaces for indentation

        Returns:
            GraphQL field selection string
        """
        lines = []
        base_indent = " " * indent

        for field in sorted(fields):
            if field in cls.GENE_NESTED_FIELDS:
                # This field requires sub-selection
                sub_fields = cls.GENE_NESTED_FIELDS[field]
                lines.append(f"{base_indent}{field} {{")
                for sub_field in sub_fields:
                    lines.append(f"{base_indent}  {sub_field}")
                lines.append(f"{base_indent}}}")
            else:
                # Simple scalar field
                lines.append(f"{base_indent}{field}")

        return "\n".join(lines)


class GraphQLQueryBuilder:
    """Builder for GraphQL queries."""

    @staticmethod
    def build_gene_query(
        fields: Union[str, List[str], None] = None,
        page: int = 0,
        limit: int = 10,
        params: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build a GraphQL query for genes.

        Args:
            fields: Field specification (see FieldSelector.expand_fields)
            page: Page number (0-based)
            limit: Number of results per page
            params: List of parameter filters, e.g., [{"key": "taxon.curie", "value": "NCBITaxon:6239"}]

        Returns:
            GraphQL query string
        """
        # Expand fields
        field_set = FieldSelector.expand_fields(fields)
        field_selection = FieldSelector.build_field_selection(field_set, indent=6)

        # Build params string
        params_str = "[]"
        if params:
            params_list = []
            for param in params:
                key = param.get("key", "")
                value = param.get("value", "")
                params_list.append(f'{{key: "{key}", value: "{value}"}}')
            params_str = f"[{', '.join(params_list)}]"

        query = f"""{{
  findGeneByParams(page: {page}, limit: {limit}, params: {params_str}) {{
    results {{
{field_selection}
    }}
    totalResults
  }}
}}"""
        return query

    @staticmethod
    def build_gene_by_id_query(gene_id: str, fields: Union[str, List[str], None] = None) -> str:
        """Build a GraphQL query for a single gene by ID.

        Args:
            gene_id: Gene ID (curie or primary external ID)
            fields: Field specification (see FieldSelector.expand_fields)

        Returns:
            GraphQL query string
        """
        # Expand fields
        field_set = FieldSelector.expand_fields(fields)
        field_selection = FieldSelector.build_field_selection(field_set, indent=4)

        query = f"""{{
  gene(id: "{gene_id}") {{
{field_selection}
  }}
}}"""
        return query

    @staticmethod
    def build_allele_query(
        fields: Union[str, List[str], None] = None,
        page: int = 0,
        limit: int = 10,
        params: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """Build a GraphQL query for alleles.

        Args:
            fields: Field specification - similar to gene fields
            page: Page number (0-based)
            limit: Number of results per page
            params: List of parameter filters

        Returns:
            GraphQL query string
        """
        # For alleles, use similar field expansion logic
        # This is a simplified version - you may want to add ALLELE_NESTED_FIELDS
        if fields is None:
            fields = [
                "primaryExternalId",
                "curie",
                "alleleSymbol",
                "alleleFullName",
                "taxon",
                "dataProvider",
                "obsolete",
            ]
        elif isinstance(fields, str):
            fields = [fields]

        # Build field selection (simplified for now)
        field_lines = []
        for field in fields:
            if field in ["alleleSymbol", "alleleFullName"]:
                field_lines.append(f"      {field} {{")
                field_lines.append("        displayText")
                field_lines.append("        formatText")
                field_lines.append("      }")
            elif field == "taxon":
                field_lines.append(f"      {field} {{")
                field_lines.append("        curie")
                field_lines.append("        name")
                field_lines.append("      }")
            elif field == "dataProvider":
                field_lines.append(f"      {field} {{")
                field_lines.append("        abbreviation")
                field_lines.append("        fullName")
                field_lines.append("      }")
            else:
                field_lines.append(f"      {field}")

        field_selection = "\n".join(field_lines)

        # Build params string
        params_str = "[]"
        if params:
            params_list = []
            for param in params:
                key = param.get("key", "")
                value = param.get("value", "")
                params_list.append(f'{{key: "{key}", value: "{value}"}}')
            params_str = f"[{', '.join(params_list)}]"

        query = f"""{{
  findAlleleByParams(page: {page}, limit: {limit}, params: {params_str}) {{
    results {{
{field_selection}
    }}
    totalResults
  }}
}}"""
        return query


def build_graphql_params(
    data_provider: Optional[str] = None, taxon: Optional[str] = None, **kwargs: Any
) -> List[Dict[str, str]]:
    """Build GraphQL params list from common filters.

    Args:
        data_provider: Data provider abbreviation (e.g., 'WB', 'MGI')
        taxon: Taxon CURIE (e.g., 'NCBITaxon:6239')
        **kwargs: Additional key-value filters

    Returns:
        List of param dictionaries for GraphQL query
    """
    params = []

    if data_provider:
        params.append({"key": "dataProvider.abbreviation", "value": data_provider})

    if taxon:
        params.append({"key": "taxon.curie", "value": taxon})

    # Add any additional filters
    for key, value in kwargs.items():
        if value is not None:
            params.append({"key": key, "value": str(value)})

    return params
