"""AGR Curation API Client.

A unified Python client for Alliance of Genome Resources (AGR) A-Team curation APIs.
"""

from .client import AGRCurationAPIClient
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
    OntologyTerm,
    ExpressionAnnotation,
    Allele,
    APIResponse,
)

__version__ = "0.1.0"
__all__ = [
    "AGRCurationAPIClient",
    "AGRAPIError",
    "AGRAuthenticationError",
    "AGRConnectionError",
    "AGRTimeoutError",
    "AGRValidationError",
    "APIConfig",
    "Gene",
    "Species",
    "OntologyTerm",
    "ExpressionAnnotation",
    "Allele",
    "APIResponse",
]
