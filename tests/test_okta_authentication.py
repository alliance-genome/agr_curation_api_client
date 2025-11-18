"""Test Okta authentication functionality."""

import os
import pytest
from agr_curation_api import AGRCurationAPIClient, APIConfig
from agr_curation_api.exceptions import AGRAuthenticationError


@pytest.mark.skipif(
    not all(
        os.environ.get(var) for var in ["OKTA_DOMAIN", "OKTA_API_AUDIENCE", "OKTA_CLIENT_ID", "OKTA_CLIENT_SECRET"]
    ),
    reason="Okta environment variables not set",
)
def test_automatic_authentication():
    """Test automatic authentication using environment variables."""
    # Create client without providing a token - should auto-authenticate
    client = AGRCurationAPIClient()

    # Try to fetch some data to verify authentication works
    species_list = client.get_species()

    assert isinstance(species_list, list)
    assert len(species_list) > 0

    # Verify species have expected attributes
    if species_list:
        first_species = species_list[0]
        assert hasattr(first_species, "abbreviation")
        assert hasattr(first_species, "display_name")


def test_missing_environment_variables():
    """Test behavior when Okta environment variables are missing."""
    # Save current environment
    saved_env = {}
    okta_vars = ["OKTA_DOMAIN", "OKTA_API_AUDIENCE", "OKTA_CLIENT_ID", "OKTA_CLIENT_SECRET"]

    for var in okta_vars:
        saved_env[var] = os.environ.get(var)
        if var in os.environ:
            del os.environ[var]

    try:
        # This should fail if environment variables are required
        with pytest.raises(Exception):  # Could be various exceptions depending on fastapi_okta implementation
            client = AGRCurationAPIClient()
            # Try to make an authenticated request
            client.get_species()
    finally:
        # Restore environment
        for var, value in saved_env.items():
            if value is not None:
                os.environ[var] = value


def test_invalid_token():
    """Test behavior with an invalid token."""
    config = APIConfig(okta_token="invalid-token")
    client = AGRCurationAPIClient(config)

    # This should raise an authentication error when trying to access the API
    with pytest.raises(AGRAuthenticationError):
        client.get_species()


@pytest.mark.parametrize(
    "endpoint,method",
    [
        ("species", "get_species"),
        ("gene/find", "get_genes"),
    ],
)
def test_authenticated_endpoints(endpoint, method):
    """Test that various endpoints require authentication."""
    # Create client with invalid token
    config = APIConfig(okta_token="invalid-token")
    client = AGRCurationAPIClient(config)

    # All endpoints should raise authentication error with invalid token
    with pytest.raises(AGRAuthenticationError):
        getattr(client, method)()
