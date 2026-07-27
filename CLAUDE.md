# AGR Curation API Client - Setup and Usage Instructions

This document provides step-by-step instructions for setting up and running the AGR Curation API client demonstration script.

## Prerequisites

- Python 3.8 or higher
- Conda package manager
- Access to the AGR development environment configuration

## Environment Setup

### 1. Create and Activate Conda Environment

The project requires a specific conda environment named `agr_curation_api_client`:

```bash
# Create the conda environment (if not already created)
conda create -n agr_curation_api_client python=3.11

# Activate the environment
conda activate agr_curation_api_client
```

### 2. Install Dependencies

Install the required Python packages:

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install the package in development mode
pip install -e .
```

### 3. Environment Variables

The script requires environment variables from the `.env.rdsdev` file. This file contains:

- API URLs and endpoints
- Authentication credentials (OKTA)
- Database connection settings
- AWS credentials
- Other service configurations

**Important**: The `.env.rdsdev` file contains sensitive information and should not be committed to version control.

## Running the Main Script

### Method 1: Using Conda Environment (Recommended)

```bash
# Navigate to the project directory
cd /home/valerio/workspace/agr/agr_curation_api_client

# Activate conda environment
conda activate agr_curation_api_client

# Set environment variables and run the script
set -a && source .env.rdsdev && set +a && python main.py
```

### Method 2: Direct Python Execution

```bash
# Navigate to the project directory
cd /home/valerio/workspace/agr/agr_curation_api_client

# Export environment variables and run with specific Python interpreter
set -a && source .env.rdsdev && set +a && /home/valerio/anaconda3/envs/agr_curation_api_client/bin/python main.py
```

## What the Script Does

The `main.py` script demonstrates the AGR Curation API client by:

1. **Initializing the API client** with configuration from environment variables
2. **Fetching and displaying various entity types**:
   - **Genes**: Protein coding and non-coding genes from various organisms
   - **Species**: Taxonomic species information
   - **Ontology Terms**: GO (Gene Ontology) terms and definitions
   - **Alleles**: Genetic variants and mutations
   - **AGMs (Affected Genomic Models)**: Disease models and genetic backgrounds
   - **Zebrafish Models**: Specific ZFIN AGM data

3. **Displaying detailed information** for each entity including:
   - Primary identifiers (CURIE, symbols)
   - Descriptive information (names, definitions)
   - Relationships (data providers, cross-references)
   - Metadata (creation dates, obsolescence status)

## Expected Output

The script will output structured information for each entity type, for example:

```
======================================================================
AGR CURATION API CLIENT DEMONSTRATION
======================================================================
Base URL: https://api.alliancegenome.org
Fetching: all entities
Limit: 10 items per type

✓ Client initialized successfully

======================================================================
FETCHING GENES
======================================================================

Found 10 gene(s)

============================================================
Gene: RpL10
============================================================
Symbol: RpL10
Taxon: Drosophila melanogaster
Type: protein_coding_gene
Obsolete: False
...
```

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Ensure `.env.rdsdev` file is present and properly formatted
   - Check OKTA credentials are valid
   - Consider setting `OKTA_TOKEN` environment variable if needed

2. **Conda Environment Issues**
   ```bash
   # If conda activate fails, initialize conda for your shell
   conda init bash
   # Then restart your shell and try again
   ```

3. **Import Errors**
   - Ensure all dependencies are installed in the correct environment
   - Verify the package is installed: `pip list | grep agr-curation-api`

4. **Network/API Issues**
   - Check internet connectivity
   - Verify API endpoints are accessible
   - Some API calls may fail due to authentication or server issues (this is expected)

### Environment Variable Issues

If you encounter issues with environment variables:

```bash
# Check if variables are set
echo $ATEAM_API_URL
echo $OKTA_CLIENT_ID

# Manual export (if sourcing fails)
export ATEAM_API_URL="https://curation.alliancegenome.org/api"
export OKTA_CLIENT_ID="your_client_id"
# ... (export other variables as needed)
```

## Development Notes

### Supported Entities

The client currently supports these AGR entities:
- ✅ Genes
- ✅ Species  
- ✅ Ontology Terms (GO)
- ✅ Alleles
- ✅ Affected Genomic Models (AGMs)
- ❌ Proteins (removed - don't exist in system)

### Configuration

The API client configuration is handled through:
- `APIConfig` class in `src/agr_curation_api/models.py`
- Environment variables (primarily from `.env.rdsdev`)
- Default values for development environment

### Logging

The client includes logging for debugging. To enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## File Structure

```
agr_curation_api_client/
├── main.py                    # Main demonstration script
├── .env.rdsdev               # Environment variables (not in git)
├── requirements.txt          # Python dependencies
├── src/
│   └── agr_curation_api/
│       ├── __init__.py       # Package initialization
│       ├── client.py         # Main API client
│       ├── models.py         # Pydantic data models
│       └── exceptions.py     # Custom exceptions
└── CLAUDE.md                 # This file
```

## Support

For issues or questions:
1. Check the console output for specific error messages
2. Verify environment setup and credentials
3. Review API documentation at Alliance of Genome Resources
4. Check network connectivity to AGR services