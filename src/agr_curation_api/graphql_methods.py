"""GraphQL methods for AGR Curation API Client.

This module contains methods that interact with the AGR Curation GraphQL API.
"""

import logging
from typing import Optional, List, Union, Any, Dict, Callable

from pydantic import ValidationError

from .models import Gene, Allele
from .graphql_queries import GraphQLQueryBuilder, build_graphql_params

logger = logging.getLogger(__name__)


class GraphQLMethods:
    """GraphQL API methods for AGR entities.

    This class contains all methods that use the GraphQL API.
    It expects to be initialized with a GraphQL request function that handles
    the actual HTTP communication.
    """

    def __init__(self, make_graphql_request_func: Callable[[str], Dict[str, Any]]) -> None:
        """Initialize GraphQL methods.

        Args:
            make_graphql_request_func: Function to make GraphQL requests
                Should have signature: func(query: str) -> Dict
        """
        self._make_graphql_request = make_graphql_request_func

    def get_genes(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        include_obsolete: bool = False,
        **filter_params: Any,
    ) -> List[Gene]:
        """Get genes using GraphQL API with flexible field selection.

        This method uses the GraphQL API instead of the REST search endpoint,
        allowing for more efficient queries by requesting only the fields you need.

        Args:
            fields: Field specification. Can be:
                - None: use "standard" preset (recommended)
                - "minimal": only essential fields (primaryExternalId, curie, geneSymbol)
                - "basic": common fields for display
                - "standard": most commonly used fields (default)
                - "full": all available fields including audit info
                - List of field names: exactly those fields
            data_provider: Filter by data provider abbreviation (e.g., 'WB', 'MGI')
            taxon: Filter by taxon CURIE (e.g., 'NCBITaxon:6239' for C. elegans)
            limit: Number of results per page
            page: Page number (0-based)
            include_obsolete: If False, filter out obsolete genes (default: False)
            **filter_params: Additional filter parameters (key=value pairs)

        Returns:
            List of Gene objects

        Example:
            # Get minimal fields for all WB genes
            genes = graphql_methods.get_genes(fields="minimal", data_provider="WB")

            # Get specific fields for C. elegans genes
            genes = graphql_methods.get_genes(
                fields=["primaryExternalId", "geneSymbol", "geneFullName"],
                taxon="NCBITaxon:6239"
            )

            # Get full details
            genes = graphql_methods.get_genes(fields="full", limit=10)
        """
        # Build GraphQL params from filters
        params = build_graphql_params(data_provider=data_provider, taxon=taxon, **filter_params)

        # Build the query
        query = GraphQLQueryBuilder.build_gene_query(
            fields=fields, page=page, limit=limit, params=params if params else None
        )

        # Execute the query
        response_data = self._make_graphql_request(query)

        # Parse results
        genes = []
        if "findGeneByParams" in response_data:
            results = response_data["findGeneByParams"].get("results", [])
            for gene_data in results:
                try:
                    gene = Gene(**gene_data)
                    # Client-side filter as safety (in case server-side filter doesn't work)
                    if not include_obsolete and hasattr(gene, "obsolete") and gene.obsolete:
                        continue
                    genes.append(gene)
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data from GraphQL: {e}")

        return genes

    def get_gene(self, gene_id: str, fields: Union[str, List[str], None] = None) -> Optional[Gene]:
        """Get a specific gene by ID using GraphQL with flexible field selection.

        Args:
            gene_id: Gene curie or primary external ID
            fields: Field specification (see get_genes for options)

        Returns:
            Gene object or None if not found

        Example:
            # Get minimal fields
            gene = graphql_methods.get_gene("WB:WBGene00000001", fields="minimal")

            # Get specific fields
            gene = graphql_methods.get_gene(
                "WB:WBGene00000001",
                fields=["primaryExternalId", "geneSymbol", "geneFullName", "taxon"]
            )
        """
        query = GraphQLQueryBuilder.build_gene_by_id_query(gene_id=gene_id, fields=fields)

        try:
            response_data = self._make_graphql_request(query)

            if "gene" in response_data and response_data["gene"]:
                return Gene(**response_data["gene"])
            return None
        except Exception:
            return None

    def get_alleles(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        **filter_params: Any,
    ) -> List[Allele]:
        """Get alleles using GraphQL API with flexible field selection.

        Args:
            fields: Field specification (None for default, list of field names, or "full")
            data_provider: Filter by data provider abbreviation
            taxon: Filter by taxon CURIE
            limit: Number of results per page
            page: Page number (0-based)
            **filter_params: Additional filter parameters

        Returns:
            List of Allele objects

        Example:
            # Get alleles with default fields from WB
            alleles = graphql_methods.get_alleles(data_provider="WB")

            # Get specific fields
            alleles = graphql_methods.get_alleles(
                fields=["primaryExternalId", "alleleSymbol", "taxon"],
                data_provider="WB"
            )
        """
        # Build GraphQL params from filters
        params = build_graphql_params(data_provider=data_provider, taxon=taxon, **filter_params)

        # Build the query
        query = GraphQLQueryBuilder.build_allele_query(
            fields=fields, page=page, limit=limit, params=params if params else None
        )

        # Execute the query
        response_data = self._make_graphql_request(query)

        # Parse results
        alleles = []
        if "findAlleleByParams" in response_data:
            results = response_data["findAlleleByParams"].get("results", [])
            for allele_data in results:
                try:
                    allele = Allele(**allele_data)
                    alleles.append(allele)
                except ValidationError as e:
                    logger.warning(f"Failed to parse allele data from GraphQL: {e}")

        return alleles
