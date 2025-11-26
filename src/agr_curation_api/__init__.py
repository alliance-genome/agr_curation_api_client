"""AGR Curation API Client.

A unified Python client for Alliance of Genome Resources (AGR) A-Team curation APIs.

This client supports multiple data access methods:
- REST API: Full-featured API with all entity types
- GraphQL: Efficient queries with flexible field selection
- Database: Direct SQL queries for high-performance bulk access
"""

from .client import AGRCurationAPIClient, DataSource
from .exceptions import (
    AGRAPIError,
    AGRAuthenticationError,
    AGRConnectionError,
    AGRTimeoutError,
    AGRValidationError,
)
from .models import (
    APIConfig,
    Gene,
    Species,
    NCBITaxonTerm,
    OntologyTerm,
    ExpressionAnnotation,
    Allele,
    APIResponse,
    CrossReference,
    DataProvider,
    SlotAnnotation,
    AffectedGenomicModel,
    DiseaseAnnotation,
)
from .graphql_queries import (
    GraphQLQueryBuilder,
    FieldSelector,
    build_graphql_params,
)
from .api_methods import APIMethods
from .graphql_methods import GraphQLMethods
from .db_methods import DatabaseMethods, DatabaseConfig

__version__ = "0.1.0"
__all__ = [
    "AGRCurationAPIClient",
    "DataSource",
    "AGRAPIError",
    "AGRAuthenticationError",
    "AGRConnectionError",
    "AGRTimeoutError",
    "AGRValidationError",
    "APIConfig",
    "Gene",
    "Species",
    "NCBITaxonTerm",
    "OntologyTerm",
    "ExpressionAnnotation",
    "Allele",
    "APIResponse",
    "CrossReference",
    "DataProvider",
    "SlotAnnotation",
    "AffectedGenomicModel",
    "DiseaseAnnotation",
    "GraphQLQueryBuilder",
    "FieldSelector",
    "build_graphql_params",
    "APIMethods",
    "GraphQLMethods",
    "DatabaseMethods",
    "DatabaseConfig",
]
