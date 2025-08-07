#!/usr/bin/env python
"""
Fetch LinkML schemas from GitHub and generate Pydantic models.

This script downloads schema files directly from the AGR GitHub repository
and generates Pydantic models with proper nested structures.
"""

import json
import logging
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Configuration
GITHUB_BASE = "https://raw.githubusercontent.com/alliance-genome/agr_curation_schema/main/model/schema"
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "src" / "agr_curation_api" / "generated_models"
CACHE_DIR = PROJECT_ROOT / ".schema_cache"

# List of schema files to fetch
SCHEMA_FILES = [
    # Core schemas
    "core.yaml",
    "allianceModel.yaml",
    "allianceMember.yaml",
    
    # Entity schemas
    "gene.yaml",
    "allele.yaml",
    "variation.yaml",
    "variantConsequence.yaml",
    "affectedGenomicModel.yaml",
    "biologicalEntitySet.yaml",
    
    # Annotation schemas
    "phenotypeAndDiseaseAnnotation.yaml",
    "expression.yaml",
    "highThroughputExpression.yaml",
    "geneInteraction.yaml",
    "modCorpusAssociation.yaml",
    "homology.yaml",
    
    # Supporting schemas
    "ontologyTerm.yaml",
    "reference.yaml",
    "resource.yaml",
    "resourceDescriptor.yaml",
    "agent.yaml",
    "controlledVocabulary.yaml",
    "image.yaml",
    "reagent.yaml",
    "curationReport.yaml",
    
    # Ingest schemas
    "ingest.yaml",
    "variantDTO.yaml",
    "bulkload.yaml",
]


def fetch_schema(filename: str, temp_dir: Path) -> bool:
    """
    Fetch a single schema file from GitHub.
    
    Args:
        filename: Name of the schema file
        temp_dir: Directory to save the file
        
    Returns:
        True if successful, False otherwise
    """
    url = f"{GITHUB_BASE}/{filename}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        output_path = temp_dir / filename
        output_path.write_text(response.text)
        
        logger.info(f"✓ Downloaded {filename}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to download {filename}: {e}")
        return False


def fetch_all_schemas() -> Optional[Path]:
    """
    Download all schema files to a temporary directory.
    
    Returns:
        Path to temporary directory containing schemas, or None if failed
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="linkml_schemas_"))
    logger.info(f"Downloading schemas to {temp_dir}")
    
    success_count = 0
    for schema_file in SCHEMA_FILES:
        if fetch_schema(schema_file, temp_dir):
            success_count += 1
    
    if success_count == 0:
        logger.error("Failed to download any schemas")
        shutil.rmtree(temp_dir)
        return None
    
    if success_count < len(SCHEMA_FILES):
        logger.warning(f"Only downloaded {success_count}/{len(SCHEMA_FILES)} schemas")
    
    return temp_dir


def generate_pydantic_models(schema_dir: Path) -> bool:
    """
    Generate Pydantic models from LinkML schemas.
    
    Args:
        schema_dir: Directory containing schema files
        
    Returns:
        True if successful, False otherwise
    """
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Main schema that imports all others
    main_schema = schema_dir / "allianceModel.yaml"
    
    if not main_schema.exists():
        logger.error("Main schema allianceModel.yaml not found")
        return False
    
    logger.info(f"Generating Pydantic models in {OUTPUT_DIR}")
    
    try:
        # Run LinkML pydantic generator
        # Generate to a single file (output goes to stdout)
        output_file = OUTPUT_DIR / "models.py"
        
        cmd = [
            "gen-pydantic",
            str(main_schema),
            "--meta", "auto",  # Include necessary metadata
            "--extra-fields", "forbid",  # Strict validation
            "--black",  # Format with black
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Generation failed: {result.stderr}")
            return False
        
        # Write the generated code to file
        output_file.write_text(result.stdout)
        
        logger.info("✓ Successfully generated Pydantic models")
        
        # Create __init__.py file
        init_file = OUTPUT_DIR / "__init__.py"
        init_content = '''"""
Auto-generated Pydantic models from LinkML schemas.

Generated: {date}
Source: {source}
"""

from pathlib import Path

# Import all generated models
__all__ = []

for py_file in Path(__file__).parent.glob("*.py"):
    if py_file.name != "__init__.py" and not py_file.name.startswith("_"):
        module_name = py_file.stem
        __all__.append(module_name)
'''.format(
            date=datetime.now().isoformat(),
            source=GITHUB_BASE
        )
        
        init_file.write_text(init_content)
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to generate models: {e}")
        return False
    except FileNotFoundError:
        logger.error("LinkML not installed. Run: pip install -r requirements.txt")
        return False


def save_metadata(schema_dir: Path):
    """Save metadata about the generation process."""
    CACHE_DIR.mkdir(exist_ok=True)
    
    metadata = {
        "generated_at": datetime.now().isoformat(),
        "source": GITHUB_BASE,
        "schemas": SCHEMA_FILES,
        "output_dir": str(OUTPUT_DIR),
    }
    
    # Try to get git commit info
    try:
        response = requests.get(
            "https://api.github.com/repos/alliance-genome/agr_curation_schema/commits/main",
            timeout=10
        )
        if response.status_code == 200:
            commit_data = response.json()
            metadata["commit_sha"] = commit_data["sha"]
            metadata["commit_date"] = commit_data["commit"]["author"]["date"]
    except:
        pass
    
    metadata_file = CACHE_DIR / "last_sync.json"
    metadata_file.write_text(json.dumps(metadata, indent=2))
    logger.info(f"✓ Saved metadata to {metadata_file}")


def cleanup(temp_dir: Optional[Path]):
    """Clean up temporary directory."""
    if temp_dir and temp_dir.exists():
        shutil.rmtree(temp_dir)
        logger.info(f"✓ Cleaned up temporary directory")


def main():
    """Main entry point."""
    logger.info("="*60)
    logger.info("LinkML to Pydantic Model Generation")
    logger.info("="*60)
    
    # Fetch schemas
    schema_dir = fetch_all_schemas()
    if not schema_dir:
        logger.error("Failed to fetch schemas")
        return 1
    
    try:
        # Generate models
        if not generate_pydantic_models(schema_dir):
            logger.error("Failed to generate models")
            return 1
        
        # Save metadata
        save_metadata(schema_dir)
        
        logger.info("="*60)
        logger.info("✅ Successfully generated Pydantic models!")
        logger.info(f"📁 Output directory: {OUTPUT_DIR}")
        logger.info("="*60)
        
        return 0
        
    finally:
        cleanup(schema_dir)


if __name__ == "__main__":
    sys.exit(main())