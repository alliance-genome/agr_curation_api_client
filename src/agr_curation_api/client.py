"""Main client for AGR Curation API with modular data source support.

This refactored client supports three data access methods:
- REST API (api): Traditional REST endpoints
- GraphQL (graphql): GraphQL API for flexible queries
- Database (db): Direct database queries via SQL
"""

import json
import logging
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union, Type, Literal
from types import TracebackType
from enum import Enum

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
from .api_methods import APIMethods
from .graphql_methods import GraphQLMethods
from .db_methods import DatabaseMethods, DatabaseConfig

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Supported data sources."""
    API = "api"
    GRAPHQL = "graphql"
    DATABASE = "db"


class AGRCurationAPIClient:
    """Client for interacting with AGR A-Team Curation API.

    This client supports multiple data access methods:
    - REST API (default): Full-featured API with all entity types
    - GraphQL: Efficient queries with flexible field selection
    - Database: Direct SQL queries for high-performance bulk access

    Args:
        config: API configuration object, dictionary, or None for defaults
        data_source: Primary data source to use ('api', 'graphql', or 'db')
            Default is 'api'. Can be overridden per method call.

    Example:
        # Use REST API (default)
        client = AGRCurationAPIClient()
        genes = client.get_genes(data_provider="WB", limit=10)

        # Use GraphQL for all requests
        client = AGRCurationAPIClient(data_source="graphql")
        genes = client.get_genes(data_provider="WB", limit=10)

        # Use direct database access
        client = AGRCurationAPIClient(data_source="db")
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=100)
    """

    def __init__(
        self,
        config: Union[APIConfig, Dict[str, Any], None] = None,
        data_source: Union[DataSource, str] = DataSource.API
    ):
        """Initialize the API client.

        Args:
            config: API configuration object, dictionary, or None for defaults
            data_source: Primary data source ('api', 'graphql', or 'db')
        """
        if config is None:
            config = APIConfig()  # type: ignore[call-arg]
        elif isinstance(config, dict):
            config = APIConfig(**config)

        self.config = config
        self.base_url = str(self.config.base_url)

        # Convert string to enum if needed
        if isinstance(data_source, str):
            data_source = DataSource(data_source.lower())
        self.data_source = data_source

        # Initialize authentication token if not provided
        if not self.config.okta_token:
            self.config.okta_token = get_authentication_token()

        # Initialize data access modules
        self._api_methods = APIMethods(self._make_request)
        self._graphql_methods = GraphQLMethods(self._make_graphql_request)
        self._db_methods = None  # Lazy initialization

    def _get_db_methods(self) -> DatabaseMethods:
        """Get or create database methods instance (lazy initialization)."""
        if self._db_methods is None:
            self._db_methods = DatabaseMethods(DatabaseConfig())
        return self._db_methods

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token."""
        if self.config.okta_token:
            headers = generate_headers(self.config.okta_token)
            return dict(headers)
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
        if self._db_methods:
            self._db_methods.close()

    def _apply_data_provider_filter(
        self,
        req_data: Dict[str, Any],
        data_provider: Optional[str],
        field_name: str = "dataProvider.abbreviation"
    ) -> None:
        """Apply data provider filter to request data."""
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
        """Apply date sorting to request data."""
        if updated_after:
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
        """Filter items by date."""
        if not updated_after:
            return items

        # Convert to datetime if needed and ensure it's timezone-aware
        if isinstance(updated_after, str):
            if 'Z' in updated_after or '+' in updated_after:
                threshold = datetime.fromisoformat(updated_after.replace('Z', '+00:00'))
            else:
                threshold = datetime.fromisoformat(updated_after).replace(tzinfo=timezone.utc)
        else:
            if updated_after.tzinfo is None:
                threshold = updated_after.replace(tzinfo=timezone.utc)
            else:
                threshold = updated_after

        filtered = []
        for item in items:
            item_date = getattr(item, date_field, None)
            if item_date:
                if isinstance(item_date, str):
                    if 'Z' in item_date or '+' in item_date:
                        item_datetime = datetime.fromisoformat(item_date.replace('Z', '+00:00'))
                    else:
                        item_datetime = datetime.fromisoformat(item_date).replace(tzinfo=timezone.utc)
                elif isinstance(item_date, datetime):
                    if item_date.tzinfo is None:
                        item_datetime = item_date.replace(tzinfo=timezone.utc)
                    else:
                        item_datetime = item_date
                else:
                    continue

                if item_datetime > threshold:
                    filtered.append(item)
            else:
                continue

        return filtered

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the A-Team API."""
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
                    return dict(json.loads(res))
                else:
                    raise AGRAPIError(f"Request failed with status: {response.getcode()}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AGRAuthenticationError("Authentication failed")
            else:
                raise AGRAPIError(f"HTTP error {e.code}: {e.reason}")
        except Exception as e:
            raise AGRAPIError(f"Request failed: {str(e)}")

    def _make_graphql_request(self, query: str) -> Dict[str, Any]:
        """Make a GraphQL request to the AGR Curation API."""
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

    # Gene methods with data source routing
    def get_genes(
        self,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        offset: Optional[int] = None,
        updated_after: Optional[Union[str, datetime]] = None,
        fields: Union[str, List[str], None] = None,
        data_source: Optional[Union[DataSource, str]] = None,
        **kwargs
    ) -> List[Gene]:
        """Get genes using the configured or specified data source.

        Args:
            data_provider: Filter by data provider abbreviation (API/GraphQL only)
            taxon: Filter by taxon CURIE (GraphQL/DB)
            limit: Number of results per page
            page: Page number (0-based, API/GraphQL only)
            offset: Number of results to skip (DB only)
            updated_after: Filter for entities updated after this date (API only)
            fields: Field specification (GraphQL only)
            data_source: Override default data source for this call
            **kwargs: Additional parameters for GraphQL

        Returns:
            List of Gene objects
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_genes(
                fields=fields,
                data_provider=data_provider,
                taxon=taxon,
                limit=limit,
                page=page,
                **kwargs
            )
        elif source == DataSource.DATABASE:
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            return self._get_db_methods().get_genes_by_taxon(
                taxon_curie=taxon,
                limit=limit,
                offset=offset
            )
        else:  # API
            return self._api_methods.get_genes(
                data_provider=data_provider,
                limit=limit,
                page=page,
                updated_after=updated_after,
                _apply_data_provider_filter=self._apply_data_provider_filter,
                _apply_date_sorting=self._apply_date_sorting,
                _filter_by_date=self._filter_by_date
            )

    def get_gene(
        self,
        gene_id: str,
        fields: Union[str, List[str], None] = None,
        data_source: Optional[Union[DataSource, str]] = None
    ) -> Optional[Gene]:
        """Get a specific gene by ID.

        Args:
            gene_id: Gene curie or primary external ID
            fields: Field specification (GraphQL only)
            data_source: Override default data source

        Returns:
            Gene object or None if not found
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_gene(gene_id, fields=fields)
        elif source == DataSource.DATABASE:
            raise AGRAPIError("Single gene lookup by ID not implemented for database source")
        else:  # API
            return self._api_methods.get_gene(gene_id)

    # Allele methods with data source routing
    def get_alleles(
        self,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        offset: Optional[int] = None,
        updated_after: Optional[Union[str, datetime]] = None,
        transgenes_only: bool = False,
        fields: Union[str, List[str], None] = None,
        data_source: Optional[Union[DataSource, str]] = None,
        **kwargs
    ) -> List[Allele]:
        """Get alleles using the configured or specified data source.

        Args:
            data_provider: Filter by data provider abbreviation
            taxon: Filter by taxon CURIE (GraphQL/DB)
            limit: Number of results per page
            page: Page number (0-based, API/GraphQL only)
            offset: Number of results to skip (DB only)
            updated_after: Filter for entities updated after this date (API only)
            transgenes_only: If True, return transgenes only (API only, WB only)
            fields: Field specification (GraphQL only)
            data_source: Override default data source
            **kwargs: Additional parameters for GraphQL

        Returns:
            List of Allele objects
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_alleles(
                fields=fields,
                data_provider=data_provider,
                taxon=taxon,
                limit=limit,
                page=page,
                **kwargs
            )
        elif source == DataSource.DATABASE:
            db_methods = self._get_db_methods()
            if taxon:
                return db_methods.get_alleles_by_taxon(
                    taxon_curie=taxon,
                    limit=limit,
                    offset=offset
                )
            elif data_provider:
                return db_methods.get_alleles_by_data_provider(
                    data_provider=data_provider,
                    limit=limit,
                    offset=offset
                )
            else:
                raise AGRAPIError("Either taxon or data_provider is required for database queries")
        else:  # API
            return self._api_methods.get_alleles(
                data_provider=data_provider,
                limit=limit,
                page=page,
                updated_after=updated_after,
                transgenes_only=transgenes_only,
                _apply_data_provider_filter=self._apply_data_provider_filter,
                _apply_date_sorting=self._apply_date_sorting,
                _filter_by_date=self._filter_by_date
            )

    def get_allele(
        self,
        allele_id: str,
        data_source: Optional[Union[DataSource, str]] = None
    ) -> Optional[Allele]:
        """Get a specific allele by ID.

        Args:
            allele_id: Allele curie or primary external ID
            data_source: Override default data source (API only)

        Returns:
            Allele object or None if not found
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.DATABASE:
            raise AGRAPIError("Single allele lookup by ID not implemented for database source")
        else:  # API (GraphQL doesn't have single allele by ID)
            return self._api_methods.get_allele(allele_id)

    # Species/Taxon methods (API only)
    def get_species(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get species data from A-Team API using NCBITaxonTerm endpoint."""
        return self._api_methods.get_species(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date
        )

    def get_ncbi_taxon_terms(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get NCBI Taxon terms from A-Team API."""
        return self._api_methods.get_ncbi_taxon_terms(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date
        )

    def get_ncbi_taxon_term(self, taxon_id: str) -> Optional[NCBITaxonTerm]:
        """Get a specific NCBI Taxon term by ID."""
        return self._api_methods.get_ncbi_taxon_term(taxon_id)

    # Ontology methods (API only)
    def get_ontology_root_nodes(self, node_type: str) -> List[OntologyTerm]:
        """Get ontology root nodes."""
        return self._api_methods.get_ontology_root_nodes(node_type)

    def get_ontology_node_children(self, node_curie: str, node_type: str) -> List[OntologyTerm]:
        """Get children of an ontology node."""
        return self._api_methods.get_ontology_node_children(node_curie, node_type)

    # Expression annotation methods (API only)
    def get_expression_annotations(
        self,
        data_provider: str,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[ExpressionAnnotation]:
        """Get expression annotations from A-Team API."""
        return self._api_methods.get_expression_annotations(
            data_provider=data_provider,
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_data_provider_filter=self._apply_data_provider_filter,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date
        )

    # AGM methods (API only)
    def get_agms(
        self,
        data_provider: Optional[str] = None,
        subtype: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[AffectedGenomicModel]:
        """Get Affected Genomic Models (AGMs) from A-Team API."""
        return self._api_methods.get_agms(
            data_provider=data_provider,
            subtype=subtype,
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_data_provider_filter=self._apply_data_provider_filter,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date
        )

    def get_agm(self, agm_id: str) -> Optional[AffectedGenomicModel]:
        """Get a specific AGM by ID."""
        return self._api_methods.get_agm(agm_id)

    def get_fish_models(
        self,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[AffectedGenomicModel]:
        """Get zebrafish AGMs from A-Team API."""
        return self._api_methods.get_fish_models(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_data_provider_filter=self._apply_data_provider_filter,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date
        )

    # Search methods (API only)
    def search_entities(
        self,
        entity_type: str,
        search_filters: Dict[str, Any],
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> APIResponse:
        """Generic search method for any entity type."""
        return self._api_methods.search_entities(
            entity_type=entity_type,
            search_filters=search_filters,
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting
        )

    # Legacy methods for backward compatibility (delegate to REST API methods)
    def get_genes_graphql(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        **filter_params
    ) -> List[Gene]:
        """Get genes using GraphQL API (legacy method for backward compatibility)."""
        return self._graphql_methods.get_genes(
            fields=fields,
            data_provider=data_provider,
            taxon=taxon,
            limit=limit,
            page=page,
            **filter_params
        )

    def get_gene_graphql(
        self,
        gene_id: str,
        fields: Union[str, List[str], None] = None
    ) -> Optional[Gene]:
        """Get a specific gene by ID using GraphQL (legacy method)."""
        return self._graphql_methods.get_gene(gene_id, fields=fields)

    def get_alleles_graphql(
        self,
        fields: Union[str, List[str], None] = None,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        **filter_params
    ) -> List[Allele]:
        """Get alleles using GraphQL API (legacy method for backward compatibility)."""
        return self._graphql_methods.get_alleles(
            fields=fields,
            data_provider=data_provider,
            taxon=taxon,
            limit=limit,
            page=page,
            **filter_params
        )