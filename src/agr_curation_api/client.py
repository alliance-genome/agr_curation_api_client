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
from enum import Enum
from types import TracebackType
from typing import Optional, Dict, Any, List, Union, Type

from fastapi_okta.okta_utils import get_authentication_token, generate_headers

from .api_methods import APIMethods
from .db_methods import DatabaseMethods, DatabaseConfig
from .exceptions import (
    AGRAPIError,
    AGRAuthenticationError,
)
from .graphql_methods import GraphQLMethods
from .models import (
    APIConfig,
    Gene,
    NCBITaxonTerm,
    OntologyTerm,
    ExpressionAnnotation,
    Allele,
    APIResponse,
    AffectedGenomicModel,
)

logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Supported data sources."""
    API = "api"
    GRAPHQL = "graphql"
    DATABASE = "db"


class AGRCurationAPIClient:
    """Client for interacting with AGR A-Team Curation API.

    This client supports multiple data access methods with automatic fallback:
    - Database: Direct SQL queries for high-performance bulk access (fastest)
    - GraphQL: Efficient queries with flexible field selection
    - REST API: Full-featured API with all entity types (fallback)

    When no data source is specified, the client automatically tries to use
    the fastest available source in order: db -> graphql -> api

    Args:
        config: API configuration object, dictionary, or None for defaults
        data_source: Primary data source to use ('api', 'graphql', 'db', or None).
            If None, auto-detects the best available source. Can be overridden per method call.

    Example:
        # Auto-detect best available data source (db -> graphql -> api)
        client = AGRCurationAPIClient()
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=10)

        # Force use of GraphQL for all requests
        client = AGRCurationAPIClient(data_source="graphql")
        genes = client.get_genes(data_provider="WB", limit=10)

        # Force use of direct database access
        client = AGRCurationAPIClient(data_source="db")
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=100)
    """

    def __init__(
        self,
        config: Union[APIConfig, Dict[str, Any], None] = None,
        data_source: Union[DataSource, str, None] = None
    ):
        """Initialize the API client.

        Args:
            config: API configuration object, dictionary, or None for defaults
            data_source: Primary data source ('api', 'graphql', or 'db').
                If None, automatically tries db -> graphql -> api in order.
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

        # Initialize data access modules
        self._api_methods = APIMethods(self._make_request)
        self._graphql_methods = GraphQLMethods(self._make_graphql_request)
        self._db_methods = None  # Lazy initialization

        # Auto-detect data source if not specified
        if data_source is None:
            self.data_source = self._auto_detect_data_source()
        else:
            # Convert string to enum if needed
            if isinstance(data_source, str):
                data_source = DataSource(data_source.lower())
            self.data_source = data_source

    def _auto_detect_data_source(self) -> DataSource:
        """Auto-detect the best available data source.

        Tries in order: db -> graphql -> api

        Returns:
            DataSource enum for the first available source
        """
        # Try database first
        try:
            db_methods = self._get_db_methods()
            # Test with a minimal query
            test_genes = db_methods.get_genes_by_taxon(
                taxon_curie="NCBITaxon:6239",
                limit=1,
                include_obsolete=False
            )
            if test_genes:
                logger.info("Auto-detected data source: database")
                return DataSource.DATABASE
        except Exception as e:
            logger.debug(f"Database not available: {e}")

        # Try GraphQL next
        try:
            # Test with a minimal GraphQL query
            test_genes = self._graphql_methods.get_genes(
                fields="minimal",
                taxon="NCBITaxon:6239",
                limit=1,
                include_obsolete=False
            )
            if test_genes:
                logger.info("Auto-detected data source: GraphQL")
                return DataSource.GRAPHQL
        except Exception as e:
            logger.debug(f"GraphQL not available: {e}")

        # Fall back to API (should always work)
        logger.info("Auto-detected data source: REST API")
        return DataSource.API

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

    def _apply_taxon_filter(
        self,
        req_data: Dict[str, Any],
        taxon: Optional[str],
        field_name: str = "taxon.curie"
    ) -> None:
        """Apply taxon filter to request data."""
        if taxon:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}

            req_data["searchFilters"]["taxonFilter"] = {
                field_name: {
                    "queryString": taxon,
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
        include_obsolete: bool = False,
        data_source: Optional[Union[DataSource, str]] = None,
        **kwargs
    ) -> List[Gene]:
        """Get genes using the configured or specified data source.

        Args:
            data_provider: Filter by data provider abbreviation (API/GraphQL)
            taxon: Filter by taxon CURIE (e.g., 'NCBITaxon:6239' for C. elegans) (API/GraphQL/DB)
            limit: Number of results per page
            page: Page number (0-based, API/GraphQL only)
            offset: Number of results to skip (DB only)
            updated_after: Filter for entities updated after this date (API only)
            fields: Field specification (GraphQL only)
            include_obsolete: If False, filter out obsolete genes (default: False)
            data_source: Override default data source for this call
            **kwargs: Additional parameters for GraphQL

        Returns:
            List of Gene objects

        Note:
            - API can filter by both data_provider (MOD abbreviation) and taxon (species)
            - GraphQL/DB filter by taxon to get consistent results across data sources
            - For C. elegans: use taxon="NCBITaxon:6239" OR data_provider="WB"
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_genes(
                fields=fields,
                data_provider=data_provider,
                taxon=taxon,
                limit=limit,
                page=page,
                include_obsolete=include_obsolete,
                **kwargs
            )
        elif source == DataSource.DATABASE:
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            return self._get_db_methods().get_genes_by_taxon(
                taxon_curie=taxon,
                limit=limit,
                offset=offset,
                include_obsolete=include_obsolete
            )
        else:  # API
            return self._api_methods.get_genes(
                data_provider=data_provider,
                taxon=taxon,
                limit=limit,
                page=page,
                updated_after=updated_after,
                include_obsolete=include_obsolete,
                _apply_data_provider_filter=self._apply_data_provider_filter,
                _apply_taxon_filter=self._apply_taxon_filter,
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
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            db_methods = self._get_db_methods()
            return db_methods.get_alleles_by_taxon(
                taxon_curie=taxon,
                limit=limit,
                offset=offset
            )
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

    # Expression annotation methods with data source routing
    def get_expression_annotations(
        self,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        data_source: Optional[Union[DataSource, str]] = None
    ) -> Union[List[ExpressionAnnotation], List[Dict[str, str]]]:
        """Get expression annotations using the configured or specified data source.

        Args:
            data_provider: Filter by data provider abbreviation (API only)
            taxon: Filter by taxon CURIE (DB only, e.g., 'NCBITaxon:6239')
            limit: Number of results per page (API only)
            page: Page number (0-based, API only)
            updated_after: Filter for entities updated after this date (API only)
            data_source: Override default data source

        Returns:
            List of ExpressionAnnotation objects (API) or List of dictionaries (DB)
            DB format: {"gene_id": str, "gene_symbol": str, "anatomy_id": str}
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        if source == DataSource.DATABASE:
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            return self._get_db_methods().get_expression_annotations(taxon_curie=taxon)
        else:  # API (GraphQL doesn't support expression annotations)
            if not data_provider:
                raise AGRAPIError("data_provider parameter is required for API queries")
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

    # Ontology relationship methods (DB only)
    def get_ontology_pairs(
        self,
        curie_prefix: str
    ) -> List[Dict[str, Any]]:
        """Get ontology term parent-child relationships from the database.

        Args:
            curie_prefix: Ontology CURIE prefix (e.g., 'DOID', 'GO')

        Returns:
            List of dictionaries containing parent-child ontology term relationships.
            Each dict contains: parent_curie, parent_name, parent_type, parent_is_obsolete,
            child_curie, child_name, child_type, child_is_obsolete, rel_type

        Example:
            pairs = client.get_ontology_pairs('DOID')
        """
        return self._get_db_methods().get_ontology_pairs(curie_prefix=curie_prefix)

    # Data provider methods (DB only)
    def get_data_providers(self) -> List[tuple]:
        """Get data providers from the database.

        Returns:
            List of tuples containing (species_display_name, taxon_curie)

        Example:
            providers = client.get_data_providers()
            # [('Caenorhabditis elegans', 'NCBITaxon:6239'), ...]
        """
        return self._get_db_methods().get_data_providers()

    # Disease annotation methods (DB only)
    def get_disease_annotations(
        self,
        taxon: str
    ) -> List[Dict[str, str]]:
        """Get disease annotations from the database.

        This retrieves disease annotations from multiple sources:
        - Direct: gene -> DO term (via genediseaseannotation)
        - Indirect from allele: gene from inferredgene_id or asserted genes
        - Indirect from AGM: gene from inferredgene_id or asserted genes
        - Disease via orthology: gene -> DO term via human orthologs

        Args:
            taxon: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239' for C. elegans)

        Returns:
            List of dictionaries containing:
            {"gene_id": str, "gene_symbol": str, "do_id": str, "relationship_type": str}

        Example:
            annotations = client.get_disease_annotations(taxon='NCBITaxon:6239')
        """
        return self._get_db_methods().get_disease_annotations(taxon_curie=taxon)

    # Ortholog methods (DB only)
    def get_best_human_orthologs_for_taxon(
        self,
        taxon: str
    ) -> Dict[str, tuple]:
        """Get the best human orthologs for all genes from a given species.

        Args:
            taxon: The taxon CURIE of the species (e.g., 'NCBITaxon:6239' for C. elegans)

        Returns:
            Dictionary mapping each gene ID to a tuple:
            (list of best human orthologs, bool indicating if any orthologs were excluded)
            Each ortholog is represented as a list: [ortholog_id, ortholog_symbol, ortholog_full_name]

        Example:
            orthologs = client.get_best_human_orthologs_for_taxon('NCBITaxon:6239')
            # {'WBGene00000001': ([['HGNC:123', 'GENE1', 'Gene 1 full name']], False), ...}
        """
        return self._get_db_methods().get_best_human_orthologs_for_taxon(taxon_curie=taxon)
