"""Exception classes for AGR Curation API Client."""

from typing import Optional, Dict, Any


class AGRAPIError(Exception):
    """Base exception for all AGR API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict[str, Any]] = None):
        """Initialize AGR API error.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
            response_data: Response data from API if available
        """
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class AGRAuthenticationError(AGRAPIError):
    """Raised when authentication fails."""

    pass


class AGRConnectionError(AGRAPIError):
    """Raised when connection to API fails."""

    pass


class AGRTimeoutError(AGRAPIError):
    """Raised when API request times out."""

    pass


class AGRValidationError(AGRAPIError):
    """Raised when request validation fails."""

    pass
