"""Main client for AGR Curation API."""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union, Type
from types import TracebackType

from pydantic import ValidationError
from fastapi_okta.okta_utils import get_authentication_token, generate_headers

from .models import (
    APIConfig,
    Gene,
    Species,
    NCBITaxonTerm,
    OntologyTerm,
    ExpressionAnnotation,
    Allele,
    APIResponse,
    AffectedGenomicModel,
)
from .exceptions import (
    AGRAPIError,
    AGRAuthenticationError,
    AGRValidationError,
)
from .graphql_queries import (
    GraphQLQueryBuilder,
    build_graphql_params,
)

logger = logging.getLogger(__name__)


class AGRCurationAPIClient:
    """Client for interacting with AGR A-Team Curation API."""

    def __init__(self, config: Union[APIConfig, Dict[str, Any], None] = None):
        """Initialize the API client.

        Args:
            config: API configuration object, dictionary, or None for defaults
        """
        if config is None:
            config = APIConfig()  # type: ignore[call-arg]
        elif isinstance(config, dict):
            config = APIConfig(**config)

        self.config = config
        self.base_url = str(self.config.base_url)

        # Initialize authentication token if not provided
        if not self.config.okta_token:
            self.config.okta_token = get_authentication_token()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token."""
        if self.config.okta_token:
            headers = generate_headers(self.config.okta_token)
            return dict(headers)  # Ensure we return Dict[str, str]
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def __enter__(self) -> "AGRCurationAPIClient":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """Context manager exit."""
        pass

    def _apply_data_provider_filter(
        self,
        req_data: Dict[str, Any],
        data_provider: Optional[str],
        field_name: str = "dataProvider.abbreviation"
    ) -> None:
        """Apply data provider filter to request data.

        Args:
            req_data: Request data dictionary to modify
            data_provider: Data provider abbreviation to filter by
            field_name: Name of the field to filter on
        """
        if data_provider:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}

            req_data["searchFilters"]["dataProviderFilter"] = {
                field_name: {
                    "queryString": data_provider,
                    "tokenOperator": "OR"
                }
            }

    def _apply_date_sorting(
        self,
        req_data: Dict[str, Any],
        updated_after: Optional[Union[str, datetime]]
    ) -> None:
        """Apply date sorting to request data.

        Args:
            req_data: Request data dictionary to modify
            updated_after: Filter for entities updated after this date (used for sorting)
        """
        if updated_after:
            # Add sort order to get newest first
            req_data["sortOrders"] = [
                {
                    "field": "dbDateUpdated",
                    "order": -1
                }
            ]

    def _filter_by_date(
        self,
        items: List[Any],
        updated_after: Optional[Union[str, datetime]],
        date_field: str = "dbDateUpdated"
    ) -> List[Any]:
        """Filter items by date.

        Args:
            items: List of items to filter
            updated_after: Filter for entities updated after this date
            date_field: Name of the date field to check

        Returns:
            Filtered list of items
        """
        if not updated_after:
            return items

        # Convert to datetime if needed and ensure it's timezone-aware
        if isinstance(updated_after, str):
            # Handle ISO format with or without timezone
            if 'Z' in updated_after or '+' in updated_after:
                threshold = datetime.fromisoformat(updated_after.replace('Z', '+00:00'))
            else:
                # Assume UTC if no timezone info
                threshold = datetime.fromisoformat(updated_after).replace(tzinfo=timezone.utc)
        else:
            # If datetime object, ensure it has timezone info
            if updated_after.tzinfo is None:
                threshold = updated_after.replace(tzinfo=timezone.utc)
            else:
                threshold = updated_after

        filtered = []
        for item in items:
            item_date = getattr(item, date_field, None)
            if item_date:
                # Convert string to datetime if needed
                if isinstance(item_date, str):
                    if 'Z' in item_date or '+' in item_date:
                        item_datetime = datetime.fromisoformat(item_date.replace('Z', '+00:00'))
                    else:
                        item_datetime = datetime.fromisoformat(item_date).replace(tzinfo=timezone.utc)
                elif isinstance(item_date, datetime):
                    # Ensure datetime has timezone info
                    if item_date.tzinfo is None:
                        item_datetime = item_date.replace(tzinfo=timezone.utc)
                    else:
                        item_datetime = item_date
                else:
                    # Skip if not a string or datetime
                    continue

                if item_datetime > threshold:
                    filtered.append(item)
            else:
                # If no date field, skip the item when filtering
                continue

        return filtered

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the A-Team API.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request data for POST requests

        Returns:
            Response data as dictionary

        Raises:
            AGRAPIError: On API errors
            AGRAuthenticationError: On authentication failures
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            if method.upper() == "GET":
                request = urllib.request.Request(url=url, headers=headers)
            else:
                request_data = json.dumps(data or {}).encode('utf-8')
                request = urllib.request.Request(
                    url=url,
                    method=method.upper(),
                    headers=headers,
                    data=request_data
                )

            with urllib.request.urlopen(request) as response:
                if response.getcode() == 200:
                    logger.debug("Request successful")
                    res = response.read().decode('utf-8')
                    return dict(json.loads(res))  # Ensure we return Dict[str, Any]
                else:
                    raise AGRAPIError(f"Request failed with status: {response.getcode()}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AGRAuthenticationError("Authentication failed")
            else:
                raise AGRAPIError(f"HTTP error {e.code}: {e.reason}")
        except Exception as e:
            raise AGRAPIError(f"Request failed: {str(e)}")

    # Gene endpoints
    def get_genes(
        self,
        data_provider: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[Gene]:
        """Get genes from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation (e.g., 'WB', 'MGI')
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of Gene objects
        """
        req_data: Dict[str, Any] = {}
        self._apply_data_provider_filter(req_data, data_provider)
        self._apply_date_sorting(req_data, updated_after)

        url = f"gene/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        genes = []
        if "results" in response_data:
            for gene_data in response_data["results"]:
                try:
                    gene = Gene(**gene_data)
                    genes.append(gene)
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data: {e}")

        # Filter by date if specified
        genes = self._filter_by_date(genes, updated_after)

        return genes

    def get_gene(self, gene_id: str) -> Optional[Gene]:
        """Get a specific gene by ID.

        Args:
            gene_id: Gene curie or primary external ID

        Returns:
            Gene object or None if not found
        """
        try:
            response_data = self._make_request("GET", f"gene/{gene_id}")
            return Gene(**response_data)
        except AGRAPIError:
            return None

    # Species endpoints (NCBITaxonTerm)
    def get_species(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get species data from A-Team API using NCBITaxonTerm endpoint.

        This method retrieves NCBI Taxonomy terms which represent species
        and other taxonomic entities.

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of NCBITaxonTerm objects representing species
        """
        req_data: Dict[str, Any] = {}
        self._apply_date_sorting(req_data, updated_after)

        url = f"ncbitaxonterm/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        species_list = []
        if "results" in response_data:
            for taxon_data in response_data["results"]:
                try:
                    species_list.append(NCBITaxonTerm(**taxon_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse NCBITaxon data: {e}")

        # Filter by date if specified
        species_list = self._filter_by_date(species_list, updated_after)

        return species_list

    def get_ncbi_taxon_terms(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get NCBI Taxon terms from A-Team API.

        This is an alias for get_species() that makes the return type clearer.
        Both methods return NCBITaxonTerm objects.

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of NCBITaxonTerm objects
        """
        return self.get_species(limit=limit, page=page, updated_after=updated_after)

    def get_ncbi_taxon_term(self, taxon_id: str) -> Optional[NCBITaxonTerm]:
        """Get a specific NCBI Taxon term by ID.

        Args:
            taxon_id: NCBI Taxon CURIE (e.g., 'NCBITaxon:9606' for human)

        Returns:
            NCBITaxonTerm object or None if not found
        """
        try:
            response_data = self._make_request("GET", f"ncbitaxonterm/{taxon_id}")
            return NCBITaxonTerm(**response_data)
        except AGRAPIError:
            return None

    # Ontology endpoints
    def get_ontology_root_nodes(self, node_type: str) -> List[OntologyTerm]:
        """Get ontology root nodes.

        Args:
            node_type: Type of ontology node (e.g., 'goterm', 'doterm', 'anatomicalterm')

        Returns:
            List of OntologyTerm objects
        """
        response_data = self._make_request("GET", f"{node_type}/rootNodes")

        terms = []
        if "entities" in response_data:
            for term_data in response_data["entities"]:
                if not term_data.get("obsolete", False):
                    try:
                        terms.append(OntologyTerm(**term_data))
                    except ValidationError as e:
                        logger.warning(f"Failed to parse ontology term: {e}")

        return terms

    def get_ontology_node_children(self, node_curie: str, node_type: str) -> List[OntologyTerm]:
        """Get children of an ontology node.

        Args:
            node_curie: CURIE of the parent node
            node_type: Type of ontology node

        Returns:
            List of child OntologyTerm objects
        """
        response_data = self._make_request("GET", f"{node_type}/{node_curie}/children")

        terms = []
        if "entities" in response_data:
            for term_data in response_data["entities"]:
                if not term_data.get("obsolete", False):
                    try:
                        terms.append(OntologyTerm(**term_data))
                    except ValidationError as e:
                        logger.warning(f"Failed to parse ontology term: {e}")

        return terms

    # Expression annotation endpoints
    def get_expression_annotations(
        self,
        data_provider: str,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[ExpressionAnnotation]:
        """Get expression annotations from A-Team API.

        Args:
            data_provider: Data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of ExpressionAnnotation objects
        """
        req_data: Dict[str, Any] = {}
        self._apply_data_provider_filter(
            req_data,
            data_provider,
            "expressionAnnotationSubject.dataProvider.abbreviation"
        )
        self._apply_date_sorting(req_data, updated_after)

        url = f"gene-expression-annotation/search?limit={limit}&page={page}"

        response_data = self._make_request("POST", url, req_data)

        annotations = []
        if "results" in response_data:
            for annotation_data in response_data["results"]:
                try:
                    annotations.append(ExpressionAnnotation(**annotation_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse expression annotation: {e}")

        # Filter by date if specified
        annotations = self._filter_by_date(annotations, updated_after)

        return annotations

    # Allele endpoints
    def get_alleles(
        self,
        data_provider: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        transgenes_only: bool = False
    ) -> List[Allele]:
        """Get alleles from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)
        transgenes_only: If True, return transgenes only (currently works for WB only

        Returns:
            List of Allele objects
        """
        if transgenes_only and data_provider != "WB":
            raise AGRAPIError("Not implemented: transgenes_only is only supported for WB data provider")

        req_data: Dict[str, Any] = {}
        self._apply_data_provider_filter(req_data, data_provider)
        self._apply_date_sorting(req_data, updated_after)

        url = f"allele/search?limit={limit}&page={page}"

        if transgenes_only and data_provider == "WB":
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}
            req_data["searchFilters"]["primaryExternalIdFilter"] = {
                "primaryExternalId": {
                    "queryString": "WB:WBTransgene",
                    "tokenOperator": "OR"
                }
            }

        response_data = self._make_request("POST", url, req_data)

        alleles = []
        if "results" in response_data:
            for allele_data in response_data["results"]:
                try:
                    alleles.append(Allele(**allele_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse allele data: {e}")

        # Filter by date if specified
        alleles = self._filter_by_date(alleles, updated_after)

        return alleles

    def get_allele(self, allele_id: str) -> Optional[Allele]:
        """Get a specific allele by ID.

        Args:
            allele_id: Allele curie or primary external ID

        Returns:
            Allele object or None if not found
        """
        try:
            response_data = self._make_request("GET", f"allele/{allele_id}")
            return Allele(**response_data)
        except AGRAPIError:
            return None

    # AGM (Affected Genomic Model) endpoints
    def get_agms(
        self,
        data_provider: Optional[str] = None,
        subtype: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[AffectedGenomicModel]:
        """Get Affected Genomic Models (AGMs) from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation (e.g., 'ZFIN' for zebrafish)
            subtype: Filter by AGM subtype name (e.g., 'strain', 'genotype')
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of AffectedGenomicModel objects
        """
        req_data: Dict[str, Any] = {}
        self._apply_data_provider_filter(req_data, data_provider)

        if subtype:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}
            req_data["searchFilters"]["subtypeFilter"] = {
                "subtype.name": {
                    "queryString": subtype,
                    "tokenOperator": "OR"
                }
            }

        self._apply_date_sorting(req_data, updated_after)

        url = f"agm/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        agms = []
        if "results" in response_data:
            for agm_data in response_data["results"]:
                try:
                    agms.append(AffectedGenomicModel(**agm_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse AGM data: {e}")

        # Filter by date if specified
        agms = self._filter_by_date(agms, updated_after)

        return agms

    def get_agm(self, agm_id: str) -> Optional[AffectedGenomicModel]:
        """Get a specific AGM by ID.

        Args:
            agm_id: AGM curie or primary external ID

        Returns:
            AffectedGenomicModel object or None if not found
        """
        try:
            response_data = self._make_request("GET", f"agm/{agm_id}")
            return AffectedGenomicModel(**response_data)
        except AGRAPIError:
            return None

    def get_fish_models(
        self,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[AffectedGenomicModel]:
        """Get zebrafish AGMs from A-Team API.

        Convenience method to get AGMs specifically for zebrafish (ZFIN).

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of AffectedGenomicModel objects for zebrafish
        """
        return self.get_agms(data_provider="ZFIN", subtype="fish", limit=limit, page=page, updated_after=updated_after)

    # GraphQL methods
    def _make_graphql_request(self, query: str) -> Dict[str, Any]:
        """Make a GraphQL request to the AGR Curation API.

        Args:
            query: GraphQL query string

        Returns:
            Response data as dictionary

        Raises:
            AGRAPIError: On API errors
            AGRAuthenticationError: On authentication failures
        """
        # GraphQL endpoint is at /graphql
        graphql_base = self.base_url.replace("/api", "")
        url = f"{graphql_base}/graphql"

        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        request_body = {"query": query}

        try:
            request_data = json.dumps(request_body).encode('utf-8')
            request = urllib.request.Request(
                url=url,
                method="POST",
                headers=headers,
                data=request_data
            )

            with urllib.request.urlopen(request) as response:
                if response.getcode() == 200:
                    logger.debug("GraphQL request successful")
                    res = response.read().decode('utf-8')
                    result = json.loads(res)

                    # Check for GraphQL errors
                    if "errors" in result:
                        error_messages = [err.get("message", str(err)) for err in result["errors"]]
                        raise AGRAPIError(f"GraphQL errors: {'; '.join(error_messages)}")

                    return result.get("data", {})
                else:
                    raise AGRAPIError(f"GraphQL request failed with status: {response.getcode()}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AGRAuthenticationError("Authentication failed")
            else:
                error_body = e.read().decode('utf-8') if e.fp else ""
                raise AGRAPIError(f"HTTP error {e.code}: {e.reason}. {error_body}")
        except AGRAPIError:
            raise
        except Exception as e:
            raise AGRAPIError(f"GraphQL request failed: {str(e)}")

    def get_genes_graphql(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        **filter_params
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
            **filter_params: Additional filter parameters (key=value pairs)

        Returns:
            List of Gene objects

        Example:
            # Get minimal fields for all WB genes
            genes = client.get_genes_graphql(fields="minimal", data_provider="WB")

            # Get specific fields for C. elegans genes
            genes = client.get_genes_graphql(
                fields=["primaryExternalId", "geneSymbol", "geneFullName"],
                taxon="NCBITaxon:6239"
            )

            # Get full details
            genes = client.get_genes_graphql(fields="full", limit=10)
        """
        # Build GraphQL params from filters
        params = build_graphql_params(
            data_provider=data_provider,
            taxon=taxon,
            **filter_params
        )

        # Build the query
        query = GraphQLQueryBuilder.build_gene_query(
            fields=fields,
            page=page,
            limit=limit,
            params=params if params else None
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
                    genes.append(gene)
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data from GraphQL: {e}")

        return genes

    def get_gene_graphql(
        self,
        gene_id: str,
        fields: Union[str, List[str], None] = None
    ) -> Optional[Gene]:
        """Get a specific gene by ID using GraphQL with flexible field selection.

        Args:
            gene_id: Gene curie or primary external ID
            fields: Field specification (see get_genes_graphql for options)

        Returns:
            Gene object or None if not found

        Example:
            # Get minimal fields
            gene = client.get_gene_graphql("WB:WBGene00000001", fields="minimal")

            # Get specific fields
            gene = client.get_gene_graphql(
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
        except AGRAPIError:
            return None

    def get_alleles_graphql(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        **filter_params
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
            alleles = client.get_alleles_graphql(data_provider="WB")

            # Get specific fields
            alleles = client.get_alleles_graphql(
                fields=["primaryExternalId", "alleleSymbol", "taxon"],
                data_provider="WB"
            )
        """
        # Build GraphQL params from filters
        params = build_graphql_params(
            data_provider=data_provider,
            taxon=taxon,
            **filter_params
        )

        # Build the query
        query = GraphQLQueryBuilder.build_allele_query(
            fields=fields,
            page=page,
            limit=limit,
            params=params if params else None
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

    # Search methods
    def search_entities(
        self,
        entity_type: str,
        search_filters: Dict[str, Any],
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> APIResponse:
        """Generic search method for any entity type.

        Args:
            entity_type: Type of entity to search (e.g., 'gene', 'allele', 'species')
            search_filters: Dictionary of search filters
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            APIResponse with search results
        """
        req_data = search_filters.copy()
        self._apply_date_sorting(req_data, updated_after)

        url = f"{entity_type}/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        try:
            return APIResponse(**response_data)
        except ValidationError as e:
            raise AGRValidationError(f"Invalid API response: {str(e)}")
