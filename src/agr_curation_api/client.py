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

    # Species endpoints
    def get_species(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[Species]:
        """Get species data from A-Team API.

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of Species objects
        """
        req_data: Dict[str, Any] = {}
        self._apply_date_sorting(req_data, updated_after)

        url = f"species/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        species_list = []
        if "results" in response_data:
            for species_data in response_data["results"]:
                try:
                    species_list.append(Species(**species_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse species data: {e}")

        # Filter by date if specified
        species_list = self._filter_by_date(species_list, updated_after)

        return species_list

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
        updated_after: Optional[Union[str, datetime]] = None
    ) -> List[Allele]:
        """Get alleles from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)

        Returns:
            List of Allele objects
        """
        req_data: Dict[str, Any] = {}
        self._apply_data_provider_filter(req_data, data_provider)
        self._apply_date_sorting(req_data, updated_after)

        url = f"allele/search?limit={limit}&page={page}"
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
