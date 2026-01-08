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
from typing import Optional, Dict, Any, List, Union, Type, Callable

from agr_cognito_py import get_authentication_token, generate_headers

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
    OntologyTermResult,
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

    When no data source is specified, each method call automatically tries the
    fastest available source in order: db -> graphql -> api. If a call fails,
    it automatically falls back to the next best source.

    Args:
        config: API configuration object, dictionary, or None for defaults
        data_source: Primary data source to use ('api', 'graphql', 'db', or None).
            If None, tries each source with automatic fallback. Can be overridden per method call.

    Example:
        # Automatic fallback per call (db -> graphql -> api)
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
        self, config: Union[APIConfig, Dict[str, Any], None] = None, data_source: Union[DataSource, str, None] = None
    ):
        """Initialize the API client.

        Args:
            config: API configuration object, dictionary, or None for defaults
            data_source: Primary data source ('api', 'graphql', or 'db').
                If None, each call will try db -> graphql -> api with automatic fallback.
        """
        if config is None:
            config = APIConfig()  # type: ignore[call-arg]
        elif isinstance(config, dict):
            config = APIConfig(**config)

        self.config = config
        self.base_url = str(self.config.base_url)

        # Authentication token is lazily initialized when needed
        self._auth_token_initialized = False

        # Initialize data access modules
        self._api_methods = APIMethods(self._make_request)
        self._graphql_methods = GraphQLMethods(self._make_graphql_request)
        self._db_methods = None  # Lazy initialization

        # Store data source preference (None means auto-fallback per call)
        if data_source is not None:
            # Convert string to enum if needed
            if isinstance(data_source, str):
                data_source = DataSource(data_source.lower())
        self.data_source = data_source

    def _get_db_methods(self) -> DatabaseMethods:
        """Get or create database methods instance (lazy initialization)."""
        if self._db_methods is None:
            self._db_methods = DatabaseMethods(DatabaseConfig())  # type: ignore[assignment]
        return self._db_methods  # type: ignore[return-value]

    def _get_auth_token(self) -> Optional[str]:
        """Get OKTA token, initializing lazily if needed.

        This method only fetches the token when first needed for API/GraphQL calls,
        allowing DB-only usage without OKTA credentials.
        """
        if not self._auth_token_initialized:
            if not self.config.auth_token:
                try:
                    self.config.auth_token = get_authentication_token()
                except Exception as e:
                    logger.warning(f"Failed to get OKTA token: {e}. API/GraphQL calls may fail.")
            self.auth_token_initialized = True
        return self.config.auth_token

    def _execute_with_fallback(
        self,
        db_func: Optional[Callable[[], Any]],
        graphql_func: Optional[Callable[[], Any]],
        api_func: Optional[Callable[[], Any]],
        method_name: str = "method",
    ) -> Any:
        """Execute a function with automatic fallback through data sources.

        Tries data sources in order: db -> graphql -> api
        Falls back to next source if current one fails.

        Args:
            db_func: Callable for database implementation (or None if not available)
            graphql_func: Callable for GraphQL implementation (or None if not available)
            api_func: Callable for API implementation (or None if not available)
            method_name: Name of the method being called (for logging)

        Returns:
            Result from the first successful data source

        Raises:
            AGRAuthenticationError: If authentication fails (not retried)
            AGRAPIError: If all available data sources fail
        """
        errors = []
        auth_error = None

        # Try database first
        if db_func is not None:
            try:
                logger.debug(f"{method_name}: Trying database")
                result = db_func()
                logger.info(f"{method_name}: Successfully used database")
                return result
            except AGRAuthenticationError as e:
                # Authentication errors should not trigger fallback
                auth_error = e
                logger.debug(f"{method_name}: Database authentication failed: {e}")
                errors.append(f"Database: {str(e)}")
            except Exception as e:
                logger.debug(f"{method_name}: Database failed: {e}")
                errors.append(f"Database: {str(e)}")

        # Try GraphQL next
        if graphql_func is not None:
            try:
                logger.debug(f"{method_name}: Trying GraphQL")
                result = graphql_func()
                logger.info(f"{method_name}: Successfully used GraphQL")
                return result
            except AGRAuthenticationError as e:
                # Authentication errors should not trigger fallback
                auth_error = e
                logger.debug(f"{method_name}: GraphQL authentication failed: {e}")
                errors.append(f"GraphQL: {str(e)}")
            except Exception as e:
                logger.debug(f"{method_name}: GraphQL failed: {e}")
                errors.append(f"GraphQL: {str(e)}")

        # Try API last
        if api_func is not None:
            try:
                logger.debug(f"{method_name}: Trying API")
                result = api_func()
                logger.info(f"{method_name}: Successfully used API")
                return result
            except AGRAuthenticationError as e:
                # Authentication errors should not trigger fallback
                auth_error = e
                logger.debug(f"{method_name}: API authentication failed: {e}")
                errors.append(f"API: {str(e)}")
            except Exception as e:
                logger.debug(f"{method_name}: API failed: {e}")
                errors.append(f"API: {str(e)}")

        # If all sources failed with authentication errors, raise authentication error
        if auth_error is not None:
            raise auth_error

        # All sources failed with other errors
        error_msg = f"{method_name}: All data sources failed. " + "; ".join(errors)
        raise AGRAPIError(error_msg)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token (lazily initialized)."""
        token = self._get_auth_token()
        if token:
            headers = generate_headers(token)
            return dict(headers)
        return {"Content-Type": "application/json", "Accept": "application/json"}

    def __enter__(self) -> "AGRCurationAPIClient":
        """Context manager entry."""
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        """Context manager exit."""
        if self._db_methods:
            self._db_methods.close()

    def _apply_data_provider_filter(
        self, req_data: Dict[str, Any], data_provider: Optional[str], field_name: str = "dataProvider.abbreviation"
    ) -> None:
        """Apply data provider filter to request data."""
        if data_provider:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}

            req_data["searchFilters"]["dataProviderFilter"] = {
                field_name: {"queryString": data_provider, "tokenOperator": "OR"}
            }

    def _apply_taxon_filter(
        self, req_data: Dict[str, Any], taxon: Optional[str], field_name: str = "taxon.curie"
    ) -> None:
        """Apply taxon filter to request data."""
        if taxon:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}

            req_data["searchFilters"]["taxonFilter"] = {field_name: {"queryString": taxon, "tokenOperator": "OR"}}

    def _apply_date_sorting(self, req_data: Dict[str, Any], updated_after: Optional[Union[str, datetime]]) -> None:
        """Apply date sorting to request data."""
        if updated_after:
            req_data["sortOrders"] = [{"field": "dbDateUpdated", "order": -1}]

    def _filter_by_date(
        self, items: List[Any], updated_after: Optional[Union[str, datetime]], date_field: str = "dbDateUpdated"
    ) -> List[Any]:
        """Filter items by date."""
        if not updated_after:
            return items

        # Convert to datetime if needed and ensure it's timezone-aware
        if isinstance(updated_after, str):
            if "Z" in updated_after or "+" in updated_after:
                threshold = datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
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
                    if "Z" in item_date or "+" in item_date:
                        item_datetime = datetime.fromisoformat(item_date.replace("Z", "+00:00"))
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
                request_data = json.dumps(data or {}).encode("utf-8")
                request = urllib.request.Request(url=url, method=method.upper(), headers=headers, data=request_data)

            with urllib.request.urlopen(request) as response:
                if response.getcode() == 200:
                    logger.debug("Request successful")
                    res = response.read().decode("utf-8")
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
            request_data = json.dumps(request_body).encode("utf-8")
            request = urllib.request.Request(url=url, method="POST", headers=headers, data=request_data)

            with urllib.request.urlopen(request) as response:
                if response.getcode() == 200:
                    logger.debug("GraphQL request successful")
                    res = response.read().decode("utf-8")
                    result = json.loads(res)

                    if "errors" in result:
                        error_messages = [err.get("message", str(err)) for err in result["errors"]]
                        raise AGRAPIError(f"GraphQL errors: {'; '.join(error_messages)}")

                    return result.get("data", {})  # type: ignore[return-value,no-any-return]
                else:
                    raise AGRAPIError(f"GraphQL request failed with status: {response.getcode()}")

        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AGRAuthenticationError("Authentication failed")
            else:
                error_body = e.read().decode("utf-8") if e.fp else ""
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
        **kwargs: Any,
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
            - When data_source is None, automatically tries db -> graphql -> api with fallback
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        # If no data source specified, use fallback mechanism
        if source is None:
            # Define functions for each data source (or None if not applicable)
            if taxon:  # Database requires taxon

                def db_func() -> List[Gene]:
                    return self._get_db_methods().get_genes_by_taxon(
                        taxon_curie=taxon, limit=limit, offset=offset, include_obsolete=include_obsolete
                    )

            else:
                db_func = None  # type: ignore[assignment]

            def graphql_func() -> List[Gene]:
                return self._graphql_methods.get_genes(
                    fields=fields,
                    data_provider=data_provider,
                    taxon=taxon,
                    limit=limit,
                    page=page,
                    include_obsolete=include_obsolete,
                    **kwargs,
                )

            def api_func() -> List[Gene]:
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
                    _filter_by_date=self._filter_by_date,
                )

            return self._execute_with_fallback(db_func, graphql_func, api_func, "get_genes")  # type: ignore[return-value,no-any-return]

        # Explicit data source specified - use that one
        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_genes(
                fields=fields,
                data_provider=data_provider,
                taxon=taxon,
                limit=limit,
                page=page,
                include_obsolete=include_obsolete,
                **kwargs,
            )
        elif source == DataSource.DATABASE:
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            return self._get_db_methods().get_genes_by_taxon(
                taxon_curie=taxon, limit=limit, offset=offset, include_obsolete=include_obsolete
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
                _filter_by_date=self._filter_by_date,
            )

    def get_gene(
        self,
        gene_id: str,
        fields: Union[str, List[str], None] = None,
        data_source: Optional[Union[DataSource, str]] = None,
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
        wb_extraction_subset: bool = False,
        fields: Union[str, List[str], None] = None,
        data_source: Optional[Union[DataSource, str]] = None,
        **kwargs: Any,
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
            wb_extraction_subset: If True, apply WB-specific filtering for allele extraction (DB only):
                - Only WB alleles (WB:WBVar prefix, excludes transgenes)
                - Excludes Million_mutation_project collection alleles
                - Excludes fallback WBVar symbols
                - Forces taxon to NCBITaxon:6239 (C. elegans)
            fields: Field specification (GraphQL only)
            data_source: Override default data source
            **kwargs: Additional parameters for GraphQL

        Returns:
            List of Allele objects

        Note:
            - When data_source is None, automatically tries db -> graphql -> api with fallback
        """
        if wb_extraction_subset:
            taxon = "NCBITaxon:6239"
        source = DataSource(data_source.lower()) if data_source else self.data_source

        # If no data source specified, use fallback mechanism
        if source is None:
            if taxon:  # Database requires taxon

                def db_func() -> List[Allele]:
                    return self._get_db_methods().get_alleles_by_taxon(
                        taxon_curie=taxon, limit=limit, offset=offset, wb_extraction_subset=wb_extraction_subset
                    )

            else:
                db_func = None  # type: ignore[assignment]

            def graphql_func() -> List[Allele]:
                return self._graphql_methods.get_alleles(
                    fields=fields, data_provider=data_provider, taxon=taxon, limit=limit, page=page, **kwargs
                )

            def api_func() -> List[Allele]:
                return self._api_methods.get_alleles(
                    data_provider=data_provider,
                    limit=limit,
                    page=page,
                    updated_after=updated_after,
                    transgenes_only=transgenes_only,
                    _apply_data_provider_filter=self._apply_data_provider_filter,
                    _apply_date_sorting=self._apply_date_sorting,
                    _filter_by_date=self._filter_by_date,
                )

            return self._execute_with_fallback(db_func, graphql_func, api_func, "get_alleles")  # type: ignore[return-value,no-any-return]

        # Explicit data source specified - use that one
        if source == DataSource.GRAPHQL:
            return self._graphql_methods.get_alleles(
                fields=fields, data_provider=data_provider, taxon=taxon, limit=limit, page=page, **kwargs
            )
        elif source == DataSource.DATABASE:
            if not taxon:
                raise AGRAPIError("taxon parameter is required for database queries")
            db_methods = self._get_db_methods()
            return db_methods.get_alleles_by_taxon(
                taxon_curie=taxon, limit=limit, offset=offset, wb_extraction_subset=wb_extraction_subset
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
                _filter_by_date=self._filter_by_date,
            )

    def get_allele(self, allele_id: str, data_source: Optional[Union[DataSource, str]] = None) -> Optional[Allele]:
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
        self, limit: int = 100, page: int = 0, updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get species data from A-Team API using NCBITaxonTerm endpoint."""
        return self._api_methods.get_species(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date,
        )

    def get_ncbi_taxon_terms(
        self, limit: int = 100, page: int = 0, updated_after: Optional[Union[str, datetime]] = None
    ) -> List[NCBITaxonTerm]:
        """Get NCBI Taxon terms from A-Team API."""
        return self._api_methods.get_ncbi_taxon_terms(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date,
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

    def get_ontology_term(self, curie: str) -> Optional[OntologyTermResult]:
        """Get a specific ontology term by CURIE from the database.

        Args:
            curie: Ontology term CURIE (e.g., 'GO:0008150', 'WBbt:0005062', 'DOID:4')

        Returns:
            OntologyTermResult object or None if not found

        Example:
            term = client.get_ontology_term('GO:0008150')
            if term:
                print(f"{term.curie}: {term.name}")
                print(f"Synonyms: {', '.join(term.synonyms)}")
        """
        return self._get_db_methods().get_ontology_term(curie)

    def get_ontology_terms(
        self, curies: List[str]
    ) -> Dict[str, Optional[OntologyTermResult]]:
        """Get multiple ontology terms by their CURIEs from the database.

        This performs a bulk lookup by CURIEs with synonym aggregation. More efficient
        than calling get_ontology_term multiple times as it uses a single SQL query.

        Args:
            curies: List of ontology term CURIEs (e.g., ['GO:0008150', 'GO:0003674'])

        Returns:
            Dictionary mapping CURIEs to OntologyTermResult objects (or None if not found)

        Example:
            terms = client.get_ontology_terms(['GO:0008150', 'GO:0003674'])
            for curie, term in terms.items():
                if term:
                    print(f"{curie}: {term.name}")
                else:
                    print(f"{curie}: Not found")
        """
        return self._get_db_methods().get_ontology_terms(curies)

    # Expression annotation methods with data source routing
    def get_expression_annotations(
        self,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        data_source: Optional[Union[DataSource, str]] = None,
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

        Note:
            - When data_source is None, automatically tries db -> api with fallback
            - GraphQL does not support expression annotations
        """
        source = DataSource(data_source.lower()) if data_source else self.data_source

        # If no data source specified, use fallback mechanism
        if source is None:
            if taxon:  # Database requires taxon

                def db_func() -> List[Dict[str, str]]:
                    return self._get_db_methods().get_expression_annotations(taxon_curie=taxon)

            else:
                db_func = None  # type: ignore[assignment]

            if data_provider:  # API requires data_provider

                def api_func() -> List[ExpressionAnnotation]:
                    return self._api_methods.get_expression_annotations(
                        data_provider=data_provider,
                        limit=limit,
                        page=page,
                        updated_after=updated_after,
                        _apply_data_provider_filter=self._apply_data_provider_filter,
                        _apply_date_sorting=self._apply_date_sorting,
                        _filter_by_date=self._filter_by_date,
                    )

            else:
                api_func = None  # type: ignore[assignment]

            return self._execute_with_fallback(db_func, None, api_func, "get_expression_annotations")  # type: ignore[return-value,no-any-return]

        # Explicit data source specified - use that one
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
                _filter_by_date=self._filter_by_date,
            )

    # AGM methods (API only)
    def get_agms(
        self,
        data_provider: Optional[str] = None,
        subtype: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
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
            _filter_by_date=self._filter_by_date,
        )

    def get_agm(self, agm_id: str) -> Optional[AffectedGenomicModel]:
        """Get a specific AGM by ID."""
        return self._api_methods.get_agm(agm_id)

    def get_fish_models(
        self, limit: int = 5000, page: int = 0, updated_after: Optional[Union[str, datetime]] = None
    ) -> List[AffectedGenomicModel]:
        """Get zebrafish AGMs from A-Team API."""
        return self._api_methods.get_fish_models(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_data_provider_filter=self._apply_data_provider_filter,
            _apply_date_sorting=self._apply_date_sorting,
            _filter_by_date=self._filter_by_date,
        )

    # Search methods (API only)
    def search_entities(
        self,
        entity_type: str,
        search_filters: Dict[str, Any],
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
    ) -> APIResponse:
        """Generic search method for any entity type."""
        return self._api_methods.search_entities(
            entity_type=entity_type,
            search_filters=search_filters,
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=self._apply_date_sorting,
        )

    # Ontology relationship methods (DB only)
    def get_ontology_pairs(self, curie_prefix: str) -> List[Dict[str, Any]]:
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
    def get_disease_annotations(self, taxon: str) -> List[Dict[str, str]]:
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
    def get_best_human_orthologs_for_taxon(self, taxon: str) -> Dict[str, tuple]:
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

    # Entity mapping methods (DB only, from agr_literature_service)
    def map_entity_names_to_curies(self, entity_type: str, entity_names: List[str], taxon: str) -> List[Dict[str, Any]]:
        """Map entity names to their CURIEs.

        Args:
            entity_type: Type of entity ('gene', 'allele', 'agm', 'construct', 'targeting reagent')
            entity_names: List of entity names/symbols to search for
            taxon: NCBI Taxon CURIE (e.g., 'NCBITaxon:6239')

        Returns:
            List of dictionaries with entity_curie, is_obsolete, entity (name) keys

        Example:
            results = client.map_entity_names_to_curies('gene', ['ACT1', 'CDC42'], 'NCBITaxon:559292')
        """
        return self._get_db_methods().map_entity_names_to_curies(
            entity_type=entity_type, entity_names=entity_names, taxon_curie=taxon
        )

    def map_entity_curies_to_info(self, entity_type: str, entity_curies: List[str]) -> List[Dict[str, Any]]:
        """Map entity CURIEs to their basic information.

        Args:
            entity_type: Type of entity ('gene', 'allele', 'agm', 'construct', 'targeting reagent')
            entity_curies: List of entity CURIEs to look up

        Returns:
            List of dictionaries with entity_curie, is_obsolete keys

        Example:
            results = client.map_entity_curies_to_info('gene', ['SGD:S000000001', 'SGD:S000000002'])
        """
        return self._get_db_methods().map_entity_curies_to_info(entity_type=entity_type, entity_curies=entity_curies)

    def map_curies_to_names(self, category: str, curies: List[str]) -> Dict[str, str]:
        """Map entity CURIEs to their display names.

        Args:
            category: Category of entity ('gene', 'allele', 'construct', 'agm', 'species', etc.)
            curies: List of CURIEs to map

        Returns:
            Dictionary mapping CURIE to display name

        Example:
            mapping = client.map_curies_to_names('gene', ['SGD:S000000001'])
            # {'SGD:S000000001': 'ACT1'}
        """
        return self._get_db_methods().map_curies_to_names(category=category, curies=curies)

    # ATP/Topic ontology methods (DB only, from agr_literature_service)
    def search_atp_topics(
        self, topic: Optional[str] = None, mod_abbr: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, str]]:
        """Search ATP ontology for topics.

        Args:
            topic: Topic name to search for (partial match, case-insensitive)
            mod_abbr: MOD abbreviation to filter by (e.g., 'WB', 'SGD')
            limit: Maximum number of results to return

        Returns:
            List of dictionaries with curie and name keys

        Example:
            topics = client.search_atp_topics(topic='development', mod_abbr='WB')
        """
        return self._get_db_methods().search_atp_topics(topic=topic, mod_abbr=mod_abbr, limit=limit)

    def get_atp_descendants(self, ancestor_curie: str, direct_children_only: bool = False) -> List[Dict[str, str]]:
        """Get descendants of an ATP ontology term.

        Args:
            ancestor_curie: ATP CURIE (e.g., 'ATP:0000002')
            direct_children_only: If True, return only direct children (distance=1).
                                  If False (default), return all descendants (transitive).

        Returns:
            List of dictionaries with curie and name keys

        Example:
            # Get all descendants (transitive)
            descendants = client.get_atp_descendants('ATP:0000002')

            # Get only direct children
            children = client.get_atp_descendants('ATP:0000002', direct_children_only=True)
        """
        return self._get_db_methods().get_atp_descendants(ancestor_curie=ancestor_curie,
                                                          direct_children_only=direct_children_only)

    def search_ontology_ancestors_or_descendants(self, ontology_node: str, direction: str = "descendants") -> List[str]:
        """Get ancestors or descendants of an ontology node.

        Args:
            ontology_node: Ontology term CURIE
            direction: 'ancestors' or 'descendants'

        Returns:
            List of CURIEs

        Example:
            desc = client.search_ontology_ancestors_or_descendants('GO:0008150', 'descendants')
        """
        return self._get_db_methods().get_ontology_ancestors_or_descendants(
            ontology_node=ontology_node, direction=direction
        )

    # Species search methods (DB only, from agr_literature_service)
    def search_species(self, species: str, limit: int = 10) -> List[Dict[str, str]]:
        """Search for species by name or CURIE.

        Args:
            species: Species name or CURIE prefix to search for
            limit: Maximum number of results

        Returns:
            List of dictionaries with curie and name keys

        Example:
            results = client.search_species('elegans')
        """
        return self._get_db_methods().search_species(species=species, limit=limit)
