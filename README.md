# AGR Curation API Client

[![Tests](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/tests.yml/badge.svg)](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/tests.yml)
[![Lint and Type Check](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/lint.yml/badge.svg)](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/lint.yml)
[![Database Integration Tests](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/database-integration-tests.yml/badge.svg)](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/database-integration-tests.yml)
[![Claude Code Review](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/claude-code-review.yml/badge.svg)](https://github.com/alliance-genome/agr_curation_api_client/actions/workflows/claude-code-review.yml)

A unified Python client for Alliance of Genome Resources (AGR) curation APIs.

## Features

- **Unified Interface**: Single client for all AGR curation API endpoints
- **Multiple Data Sources**: Supports REST API, GraphQL, and direct database access
- **Type Safety**: Full type hints and Pydantic models for request/response validation
- **Entity Search**: Partial matching and synonym search for genes, alleles, and other entities
- **Ontology Search**: Comprehensive search across 45 ontology types (GO, DO, HP, and more)
- **Disease Annotations**: Query disease associations for genes, alleles, and AGMs across all MODs
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

### Data Source Selection

The client supports multiple data access methods with automatic fallback. By default, it tries database access first (fastest), then GraphQL, then REST API.

```python
# Automatic data source selection (default behavior)
client = AGRCurationAPIClient()
genes = client.get_genes(taxon="NCBITaxon:6239", limit=100)  # Uses database if available

# Force specific data source
client = AGRCurationAPIClient(data_source="db")      # Database only
client = AGRCurationAPIClient(data_source="graphql") # GraphQL only
client = AGRCurationAPIClient(data_source="api")     # REST API only

# Direct database access for advanced queries
gene = client.db.get_gene("WB:WBGene00001234")
allele = client.db.get_allele("WB:WBVar00001234")
```

### Working with Genes

```python
from agr_curation_api import AGRCurationAPIClient, Gene

# Use default configuration
client = AGRCurationAPIClient()

# Get genes from a specific data provider
wb_genes = client.get_genes(data_provider="WB", limit=100)
print(f"Found {len(wb_genes)} WormBase genes")

# Get a specific gene by ID (works with database, GraphQL, or API)
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

### Working with Disease Annotations

The client provides comprehensive disease annotation queries supporting gene, allele, and AGM (affected genomic model) disease associations.

```python
from agr_curation_api import DatabaseMethods

db = DatabaseMethods()

# Get disease annotations for a specific gene
annotations = db.get_disease_annotations_by_gene("WB:WBGene00004271")  # rab-7

for ann in annotations:
    print(f"Disease: {ann.disease_name} ({ann.disease_curie})")
    print(f"  Relation: {ann.relation}")
    print(f"  Reference: {ann.reference_curie}")

# Include ECO evidence codes
annotations = db.get_disease_annotations_by_gene(
    "WB:WBGene00004271",
    include_evidence_codes=True
)

for ann in annotations:
    if ann.evidence_codes:
        print(f"Evidence: {', '.join(ann.evidence_codes)}")

# Get disease annotations by species and annotation type
# annotation_type: "gene", "allele", or "agm"
worm_gene_diseases = db.get_disease_annotations_by_taxon(
    "NCBITaxon:6239",           # C. elegans
    annotation_type="gene",
    limit=100
)

# Mouse uses allele-level annotations (not gene-level)
mouse_allele_diseases = db.get_disease_annotations_by_taxon(
    "NCBITaxon:10090",          # M. musculus
    annotation_type="allele",
    limit=100
)

# FlyBase uses AGM-level annotations
fly_agm_diseases = db.get_disease_annotations_by_taxon(
    "NCBITaxon:7227",           # D. melanogaster
    annotation_type="agm",
    limit=100
)

# Get annotations for a specific disease
obesity_annotations = db.get_disease_annotations_by_disease(
    "DOID:9970",                # obesity
    annotation_type="gene",     # optional filter
    limit=50
)

# Lightweight dictionary output for performance
raw_results = db.get_disease_annotations_raw(
    "NCBITaxon:6239",
    annotation_type="gene",
    limit=100
)

for r in raw_results:
    print(f"{r['subject_id']}: {r['disease_name']}")
```

**Note on Data Provider Coverage:**

Different MODs submit disease annotations at different levels:

| Provider | Gene | Allele | AGM |
|----------|:----:|:------:|:---:|
| Human (OMIM) | ✓ | - | - |
| Rat (RGD) | ✓ | ✓ | ✓ |
| Yeast (SGD) | ✓ | - | - |
| C. elegans (WB) | ✓ | ✓ | ✓ |
| Mouse (MGI) | - | ✓ | ✓ |
| Fly (FB) | - | - | ✓ |
| Zebrafish (ZFIN) | - | - | ✓ |

### Working with Alleles

```python
# Get alleles from a specific data provider
wb_alleles = client.get_alleles(data_provider="WB", limit=50)

for allele in wb_alleles:
    symbol = allele.allele_symbol.get("displayText", "") if allele.allele_symbol else ""
    print(f"{allele.curie}: {symbol}")

# Get a specific allele by ID (works with database, GraphQL, or API)
allele = client.get_allele("WB:WBVar00001234")
if allele:
    print(f"Allele: {allele.allele_symbol}")
    print(f"Full name: {allele.allele_full_name}")
    print(f"Extinction status: {allele.is_extinct}")
```

### Searching Entities

The client provides two search methods with different strengths:

**Entity Search** (`search_entities`): Best for user-friendly, autocomplete-style searching
- Database-only (direct SQL queries)
- Partial text matching: "rut" finds "rutabaga", "RUT", "rut-1"
- Automatically searches symbols, full names, and synonyms
- Returns results with relevance scoring (exact > starts-with > contains)
- Use when: searching by partial names, building autocomplete, finding entities by common/historical names
- Supported types: gene, allele, agm, strain, genotype, fish

**Generic Search** (`search_entities`): Best for programmatic queries with known field structures
- REST API-based with structured filters
- Exact field matching with precise field paths (e.g., "geneSymbol.displayText")
- Supports complex boolean filter logic
- Returns complete entity objects
- Use when: you know exact field names, need complex filters, require full entity data
- Supports all entity types available in the API

### Entity Search

```python
# Search for genes with partial matching
# Example: Find genes containing "rut" in Drosophila
results = client.db.search_entities(
    entity_type='gene',
    search_pattern='rut',
    taxon_curie='NCBITaxon:7227',
    include_synonyms=True,
    limit=10
)

for result in results:
    print(f"{result['entity_curie']}: {result['entity']}")
    print(f"  Match type: {result['match_type']}")  # exact, starts_with, or contains
    print(f"  Relevance: {result['relevance']}")    # 1 (best) to 3 (least)

# Search for alleles without synonyms
allele_results = client.db.search_entities(
    entity_type='allele',
    search_pattern='daf',
    taxon_curie='NCBITaxon:6239',
    include_synonyms=False,
    limit=20
)

# Supported entity types: 'gene', 'allele', 'agm', 'strain', 'genotype', 'fish'
# Results are ordered by relevance (exact matches first, then starts-with, then contains)
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

### Ontology Term Search

The client provides comprehensive ontology term search with support for 45 different ontology types including GO, DO, HPTerm, and many more.

```python
# Search Gene Ontology terms
go_results = client.db.search_ontology_terms(
    term='apoptosis',
    ontology_type='GOTerm',
    include_synonyms=True,
    limit=10
)

for result in go_results:
    print(f"{result.curie}: {result.name}")
    print(f"  Namespace: {result.namespace}")
    print(f"  Synonyms: {', '.join(result.synonyms[:3])}")

# Search Disease Ontology with exact matching
disease_results = client.db.search_ontology_terms(
    term='diabetes',
    ontology_type='DOTerm',
    exact_match=True,  # Only exact matches
    limit=5
)

# Organism-specific convenience methods
# Search C. elegans anatomy terms
wb_anatomy = client.db.search_anatomy_terms(
    term='pharynx',
    data_provider='WB',  # C. elegans
    limit=5
)

# Search Mouse life stages
mouse_stages = client.db.search_life_stage_terms(
    term='embryonic',
    data_provider='MGI',  # Mouse
    limit=5
)

# Search GO terms by aspect
cellular_components = client.db.search_go_terms(
    term='nucleus',
    go_aspect='cellular_component',  # or 'biological_process', 'molecular_function'
    limit=10
)

# Other convenience methods:
# - search_disease_terms() - Disease Ontology (DO)
# - search_phenotype_terms() - Phenotype ontologies (HP, MP, WBPhenotype)
# - search_chemical_terms() - ChEBI chemical entities
# - search_evidence_terms() - Evidence & Conclusion Ontology (ECO)
# - search_taxon_terms() - NCBI Taxonomy
# - search_sequence_terms() - Sequence Ontology (SO)
```

Supported ontology types include: APOTerm, ATPTerm, BSPOTerm, BTOTerm, CHEBITerm, CLTerm, CMOTerm, DAOTerm, DOTerm, ECOTerm, EMAPATerm, FBCVTerm, FBDVTerm, GENOTerm, GOTerm, HPTerm, MATerm, MITerm, MMOTerm, MMUSDVTerm, MODTerm, Molecule, MPATHTerm, MPTerm, NCBITaxonTerm, OBITerm, PATOTerm, PWTerm, ROTerm, RSTerm, SOTerm, UBERONTerm, VTTerm, WBBTTerm, WBLSTerm, WBPhenotypeTerm, XBATerm, XBEDTerm, XBSTerm, XCOTerm, XPOTerm, XSMOTerm, ZECOTerm, ZFATerm, ZFSTerm.

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
