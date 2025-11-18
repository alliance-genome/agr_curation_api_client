"""REST API methods for AGR Curation API Client.

This module contains methods that interact with the AGR Curation REST API endpoints.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Union, Callable

from pydantic import ValidationError

from .models import (
    Gene,
    NCBITaxonTerm,
    OntologyTerm,
    ExpressionAnnotation,
    Allele,
    AffectedGenomicModel,
    APIResponse,
)
from .exceptions import AGRValidationError

logger = logging.getLogger(__name__)


class APIMethods:
    """REST API methods for AGR entities.

    This class contains all methods that use the REST API endpoints.
    It expects to be initialized with a request function that handles
    the actual HTTP communication.
    """

    def __init__(self, make_request_func: Callable[..., Dict[str, Any]]) -> None:
        """Initialize API methods.

        Args:
            make_request_func: Function to make HTTP requests
                Should have signature: func(method: str, endpoint: str, data: Optional[Dict]) -> Dict
        """
        self._make_request = make_request_func

    # Gene endpoints
    def get_genes(
        self,
        data_provider: Optional[str] = None,
        taxon: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        include_obsolete: bool = False,
        _apply_data_provider_filter: Optional[Callable[..., None]] = None,
        _apply_taxon_filter: Optional[Callable[..., None]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[Gene]:
        """Get genes from REST API.

        Args:
            data_provider: Filter by data provider abbreviation (e.g., 'WB', 'MGI')
            taxon: Filter by taxon CURIE (e.g., 'NCBITaxon:6239')
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)
            include_obsolete: If False, filter out obsolete genes (default: False)
            _apply_data_provider_filter: Helper function for applying data provider filter
            _apply_taxon_filter: Helper function for applying taxon filter
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of Gene objects
        """
        req_data: Dict[str, Any] = {}
        if _apply_data_provider_filter:
            _apply_data_provider_filter(req_data, data_provider)
        if _apply_taxon_filter:
            _apply_taxon_filter(req_data, taxon)
        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

        url = f"gene/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        genes = []
        if "results" in response_data:
            for gene_data in response_data["results"]:
                try:
                    gene = Gene(**gene_data)
                    # Filter obsolete genes if requested
                    if not include_obsolete and gene.obsolete:
                        continue
                    genes.append(gene)
                except ValidationError as e:
                    logger.warning(f"Failed to parse gene data: {e}")

        # Filter by date if specified
        if _filter_by_date and updated_after:
            genes = _filter_by_date(genes, updated_after)

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
        except Exception:
            return None

    # Species endpoints (NCBITaxonTerm)
    def get_species(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[NCBITaxonTerm]:
        """Get species data from REST API using NCBITaxonTerm endpoint.

        This method retrieves NCBI Taxonomy terms which represent species
        and other taxonomic entities.

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date (ISO format string or datetime)
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of NCBITaxonTerm objects representing species
        """
        req_data: Dict[str, Any] = {}
        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

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
        if _filter_by_date and updated_after:
            species_list = _filter_by_date(species_list, updated_after)

        return species_list

    def get_ncbi_taxon_terms(
        self,
        limit: int = 100,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[NCBITaxonTerm]:
        """Get NCBI Taxon terms from REST API.

        This is an alias for get_species() that makes the return type clearer.

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of NCBITaxonTerm objects
        """
        return self.get_species(
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_date_sorting=_apply_date_sorting,
            _filter_by_date=_filter_by_date,
        )

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
        except Exception:
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
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_data_provider_filter: Optional[Callable[..., None]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[ExpressionAnnotation]:
        """Get expression annotations from REST API.

        Args:
            data_provider: Data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            _apply_data_provider_filter: Helper function for applying data provider filter
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of ExpressionAnnotation objects
        """
        req_data: Dict[str, Any] = {}
        if _apply_data_provider_filter:
            _apply_data_provider_filter(
                req_data, data_provider, "expressionAnnotationSubject.dataProvider.abbreviation"
            )
        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

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
        if _filter_by_date and updated_after:
            annotations = _filter_by_date(annotations, updated_after)

        return annotations

    # Allele endpoints
    def get_alleles(
        self,
        data_provider: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        transgenes_only: bool = False,
        _apply_data_provider_filter: Optional[Callable[..., None]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[Allele]:
        """Get alleles from REST API.

        Args:
            data_provider: Filter by data provider abbreviation
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            transgenes_only: If True, return transgenes only (currently works for WB only)
            _apply_data_provider_filter: Helper function for applying data provider filter
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of Allele objects
        """
        from .exceptions import AGRAPIError

        if transgenes_only and data_provider != "WB":
            raise AGRAPIError("Not implemented: transgenes_only is only supported for WB data provider")

        req_data: Dict[str, Any] = {}
        if _apply_data_provider_filter:
            _apply_data_provider_filter(req_data, data_provider)
        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

        url = f"allele/search?limit={limit}&page={page}"

        if transgenes_only and data_provider == "WB":
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}
            req_data["searchFilters"]["primaryExternalIdFilter"] = {
                "primaryExternalId": {"queryString": "WB:WBTransgene", "tokenOperator": "OR"}
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
        if _filter_by_date and updated_after:
            alleles = _filter_by_date(alleles, updated_after)

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
        except Exception:
            return None

    # AGM (Affected Genomic Model) endpoints
    def get_agms(
        self,
        data_provider: Optional[str] = None,
        subtype: Optional[str] = None,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_data_provider_filter: Optional[Callable[..., None]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[AffectedGenomicModel]:
        """Get Affected Genomic Models (AGMs) from REST API.

        Args:
            data_provider: Filter by data provider abbreviation (e.g., 'ZFIN' for zebrafish)
            subtype: Filter by AGM subtype name (e.g., 'strain', 'genotype')
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            _apply_data_provider_filter: Helper function for applying data provider filter
            _apply_date_sorting: Helper function for applying date sorting
            _filter_by_date: Helper function for filtering by date

        Returns:
            List of AffectedGenomicModel objects
        """
        req_data: Dict[str, Any] = {}
        if _apply_data_provider_filter:
            _apply_data_provider_filter(req_data, data_provider)

        if subtype:
            if "searchFilters" not in req_data:
                req_data["searchFilters"] = {}
            req_data["searchFilters"]["subtypeFilter"] = {
                "subtype.name": {"queryString": subtype, "tokenOperator": "OR"}
            }

        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

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
        if _filter_by_date and updated_after:
            agms = _filter_by_date(agms, updated_after)

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
        except Exception:
            return None

    def get_fish_models(
        self,
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_data_provider_filter: Optional[Callable[..., None]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
        _filter_by_date: Optional[Callable[..., Any]] = None,
    ) -> List[AffectedGenomicModel]:
        """Get zebrafish AGMs from REST API.

        Convenience method to get AGMs specifically for zebrafish (ZFIN).

        Args:
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            _apply_data_provider_filter: Helper function
            _apply_date_sorting: Helper function
            _filter_by_date: Helper function

        Returns:
            List of AffectedGenomicModel objects for zebrafish
        """
        return self.get_agms(
            data_provider="ZFIN",
            subtype="fish",
            limit=limit,
            page=page,
            updated_after=updated_after,
            _apply_data_provider_filter=_apply_data_provider_filter,
            _apply_date_sorting=_apply_date_sorting,
            _filter_by_date=_filter_by_date,
        )

    # Search methods
    def search_entities(
        self,
        entity_type: str,
        search_filters: Dict[str, Any],
        limit: int = 5000,
        page: int = 0,
        updated_after: Optional[Union[str, datetime]] = None,
        _apply_date_sorting: Optional[Callable[..., None]] = None,
    ) -> APIResponse:
        """Generic search method for any entity type.

        Args:
            entity_type: Type of entity to search (e.g., 'gene', 'allele', 'species')
            search_filters: Dictionary of search filters
            limit: Number of results per page
            page: Page number (0-based)
            updated_after: Filter for entities updated after this date
            _apply_date_sorting: Helper function for applying date sorting

        Returns:
            APIResponse with search results
        """
        req_data = search_filters.copy()
        if _apply_date_sorting:
            _apply_date_sorting(req_data, updated_after)

        url = f"{entity_type}/search?limit={limit}&page={page}"
        response_data = self._make_request("POST", url, req_data)

        try:
            return APIResponse(**response_data)
        except ValidationError as e:
            raise AGRValidationError(f"Invalid API response: {str(e)}")
