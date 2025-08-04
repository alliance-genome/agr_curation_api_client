# AGR Curation API Client

A unified Python client for Alliance of Genome Resources (AGR) curation APIs.

## Features

- **Unified Interface**: Single client for all AGR curation API endpoints
- **Type Safety**: Full type hints and Pydantic models for request/response validation
- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Authentication**: Support for API key and Okta token authentication
- **Async Support**: Built on httpx for both sync and async operations
- **Comprehensive Error Handling**: Detailed exceptions for different error scenarios

## Installation

```bash
pip install agr-curation-api-client
```

For development:
```bash
git clone https://github.com/alliance-genome/agr_curation_api_client.git
cd agr_curation_api_client
make install-dev
```

## Authentication

The client supports automatic Okta token generation using the same environment variables as other AGR services:

```bash
export OKTA_DOMAIN="your-okta-domain"
export OKTA_API_AUDIENCE="your-api-audience"
export OKTA_CLIENT_ID="your-client-id"
export OKTA_CLIENT_SECRET="your-client-secret"
```

With these environment variables set, the client will automatically obtain an authentication token when initialized.

## Quick Start

### Basic Usage

```python
from agr_curation_api import AGRCurationAPIClient, APIConfig

# Option 1: Automatic authentication (requires OKTA env vars)
client = AGRCurationAPIClient()

# Option 2: Manual token configuration
config = APIConfig(
    base_url="https://curation.alliancegenome.org/api",
    okta_token="your-okta-token"  # Optional - will auto-retrieve if not provided
)
client = AGRCurationAPIClient(config)

# Use the client
with client:
    # Get genes from WormBase
    genes = client.get_genes(data_provider="WB", limit=10)
    
    for gene in genes:
        symbol = gene.gene_symbol.get("displayText", "") if gene.gene_symbol else ""
        print(f"{gene.curie}: {symbol}")
```

### Working with Genes

```python
from agr_curation_api import AGRCurationAPIClient, Gene

# Use default configuration
client = AGRCurationAPIClient()

# Get genes from a specific data provider
wb_genes = client.get_genes(data_provider="WB", limit=100)
print(f"Found {len(wb_genes)} WormBase genes")

# Get a specific gene by ID
gene = client.get_gene("WB:WBGene00001234")
if gene:
    print(f"Gene: {gene.gene_symbol}")
    print(f"Full name: {gene.gene_full_name}")
    print(f"Species: {gene.taxon}")

# Get all genes (paginated)
all_genes = client.get_genes(limit=5000, page=0)
```

### Working with Species

```python
# Get all species
species_list = client.get_species()

for species in species_list:
    print(f"{species.abbreviation}: {species.display_name}")

# Find a specific species
wb_species = [s for s in species_list if s.abbreviation == "WB"]
if wb_species:
    print(f"WormBase: {wb_species[0].full_name}")
```

### Working with Ontology Terms

```python
# Get GO term root nodes
go_roots = client.get_ontology_root_nodes("goterm")
print(f"Found {len(go_roots)} GO root terms")

# Get children of a specific GO term
children = client.get_ontology_node_children("GO:0008150", "goterm")  # biological_process
for child in children:
    print(f"{child.curie}: {child.name}")

# Get disease ontology terms
disease_roots = client.get_ontology_root_nodes("doterm")

# Get anatomical terms
anatomy_roots = client.get_ontology_root_nodes("anatomicalterm")
```

### Working with Expression Annotations

```python
# Get expression annotations for WormBase
wb_expressions = client.get_expression_annotations(
    data_provider="WB",
    limit=100
)

for expr in wb_expressions:
    if expr.expression_annotation_subject:
        gene_id = expr.expression_annotation_subject.get("primaryExternalId")
        gene_symbol = expr.expression_annotation_subject.get("geneSymbol", {}).get("displayText")
        print(f"Gene: {gene_id} ({gene_symbol})")
        
    if expr.expression_pattern:
        anatomy = expr.expression_pattern.get("whereExpressed", {}).get("anatomicalStructure", {}).get("curie")
        print(f"  Expressed in: {anatomy}")
```

### Working with Alleles

```python
# Get alleles from a specific data provider
wb_alleles = client.get_alleles(data_provider="WB", limit=50)

for allele in wb_alleles:
    symbol = allele.allele_symbol.get("displayText", "") if allele.allele_symbol else ""
    print(f"{allele.curie}: {symbol}")

# Get a specific allele
allele = client.get_allele("WB:WBVar00001234")
if allele:
    print(f"Allele: {allele.allele_symbol}")
    print(f"Full name: {allele.allele_full_name}")
```

### Generic Search

```python
# Generic entity search
search_filters = {
    "dataProvider.abbreviation": "WB",
    "geneSymbol.displayText": "daf-16"
}

results = client.search_entities(
    entity_type="gene",
    search_filters=search_filters,
    limit=10
)

print(f"Total results: {results.total_results}")
print(f"Returned: {results.returned_records}")

for gene_data in results.results:
    print(f"Found gene: {gene_data}")
```

### Error Handling

```python
from agr_curation_api import (
    AGRAPIError,
    AGRAuthenticationError,
    AGRConnectionError,
    AGRTimeoutError,
    AGRValidationError
)

try:
    reference = client.get_reference("invalid-id")
except AGRAuthenticationError:
    print("Authentication failed - check your credentials")
except AGRValidationError as e:
    print(f"Invalid data: {e}")
except AGRTimeoutError:
    print("Request timed out - try again later")
except AGRConnectionError:
    print("Connection failed - check network")
except AGRAPIError as e:
    print(f"API error: {e}")
    if e.status_code:
        print(f"Status code: {e.status_code}")
```

## Configuration Options

The `APIConfig` class supports the following options:

- `base_url`: Base URL for the A-Team Curation API (default: "https://curation.alliancegenome.org/api")
- `okta_token`: Okta bearer token for authentication (auto-retrieved if not provided)
- `timeout`: Request timeout in seconds (default: 30)
- `max_retries`: Maximum retry attempts (default: 3)
- `retry_delay`: Initial delay between retries in seconds (default: 1)
- `verify_ssl`: Whether to verify SSL certificates (default: True)
- `headers`: Additional headers to include in requests

### Environment Variables

The client uses the following environment variables for configuration:

- `ATEAM_API`: Override the default A-Team API URL (default: uses production curation API)
- `OKTA_DOMAIN`: Your Okta domain (required for automatic authentication)
- `OKTA_API_AUDIENCE`: Your API audience (required for automatic authentication)
- `OKTA_CLIENT_ID`: Your Okta client ID (required for automatic authentication)
- `OKTA_CLIENT_SECRET`: Your Okta client secret (required for automatic authentication)

## Development

### Running Tests

```bash
make test
```

### Code Quality

```bash
# Run linting
make lint

# Run type checking
make type-check

# Format code
make format

# Run all checks
make check
```

### Building Documentation

```bash
cd docs
make html
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/alliance-genome/agr_curation_api_client/issues)
- **Documentation**: [API Documentation](https://alliancegenome.org/api-docs)
- **Contact**: software@alliancegenome.org
