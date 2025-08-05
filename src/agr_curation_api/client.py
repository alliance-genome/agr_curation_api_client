"""Main client for AGR Curation API."""

import json
import logging
import urllib.request
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
        page: int = 0
    ) -> List[Gene]:
        """Get genes from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation (e.g., 'WB', 'MGI')
            limit: Number of results per page
            page: Page number (0-based)

        Returns:
            List of Gene objects
        """
        req_data = {}
        if data_provider:
            req_data["dataProvider.abbreviation"] = data_provider

        url = f"gene/find?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        genes = []
        if "results" in response_data:
            for gene_data in response_data["results"]:
                try:
                    genes.append(Gene(**gene_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data: {e}")

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
    def get_species(self, limit: int = 100, page: int = 0) -> List[Species]:
        """Get species data from A-Team API.

        Args:
            limit: Number of results per page
            page: Page number (0-based)

        Returns:
            List of Species objects
        """
        url = f"species/findForPublic?limit={limit}&page={page}&view=ForPublic"
        response_data = self._make_request("POST", url, {})

        species_list = []
        if "results" in response_data:
            for species_data in response_data["results"]:
                try:
                    species_list.append(Species(**species_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse species data: {e}")

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
        page: int = 0
    ) -> List[ExpressionAnnotation]:
        """Get expression annotations from A-Team API.

        Args:
            data_provider: Data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)

        Returns:
            List of ExpressionAnnotation objects
        """
        req_data = {"expressionAnnotationSubject.dataProvider.abbreviation": data_provider}
        url = f"gene-expression-annotation/findForPublic?limit={limit}&page={page}&view=ForPublic"

        response_data = self._make_request("POST", url, req_data)

        annotations = []
        if "results" in response_data:
            for annotation_data in response_data["results"]:
                try:
                    annotations.append(ExpressionAnnotation(**annotation_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse expression annotation: {e}")

        return annotations

    # Allele endpoints
    def get_alleles(
        self,
        data_provider: Optional[str] = None,
        limit: int = 5000,
        page: int = 0
    ) -> List[Allele]:
        """Get alleles from A-Team API.

        Args:
            data_provider: Filter by data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)

        Returns:
            List of Allele objects
        """
        req_data = {}
        if data_provider:
            req_data["dataProvider.abbreviation"] = data_provider

        url = f"allele/find?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        alleles = []
        if "results" in response_data:
            for allele_data in response_data["results"]:
                try:
                    alleles.append(Allele(**allele_data))
                except ValidationError as e:
                    logger.warning(f"Failed to parse allele data: {e}")

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

    # Search methods
    def search_entities(
        self,
        entity_type: str,
        search_filters: Dict[str, Any],
        limit: int = 5000,
        page: int = 0
    ) -> APIResponse:
        """Generic search method for any entity type.

        Args:
            entity_type: Type of entity to search (e.g., 'gene', 'allele', 'species')
            search_filters: Dictionary of search filters
            limit: Number of results per page
            page: Page number (0-based)

        Returns:
            APIResponse with search results
        """
        url = f"{entity_type}/find?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, search_filters)

        try:
            return APIResponse(**response_data)
        except ValidationError as e:
            raise AGRValidationError(f"Invalid API response: {str(e)}")
