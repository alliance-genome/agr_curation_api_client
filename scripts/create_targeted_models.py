#!/usr/bin/env python3
"""
Create targeted Pydantic models for only the objects we need.

This bypasses LinkML generation complexity by creating a minimal, targeted approach
that generates only the specific models needed for the current API.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

import yaml

def create_super_minimal_schema() -> Dict[str, Any]:
    """Create the most minimal schema possible with only our needed objects."""
    
    return {
        "id": "https://github.com/alliance-genome/agr_curation_schema/targeted.yaml",
        "name": "targeted_agr_schema", 
        "description": "Targeted minimal schema for AGR API client",
        "default_prefix": "alliance",
        "default_range": "string",
        "imports": ["linkml:types"],
        "prefixes": {
            "alliance": "http://alliancegenome.org/",
            "linkml": "https://w3id.org/linkml/",
            "SO": "http://purl.obolibrary.org/obo/SO_",
            "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_"
        },
        
        "classes": {
            # Base object - no inheritance issues
            "SlotAnnotation": {
                "description": "Base class for slot annotations with evidence",
                "attributes": {
                    "evidence": {"range": "string", "multivalued": True, "required": False},
                    "internal": {"range": "boolean", "required": False},
                    "obsolete": {"range": "boolean", "required": False}
                }
            },
            
            # Name annotation - simple inheritance
            "NameSlotAnnotation": {
                "description": "Name/symbol annotation with display text",
                "is_a": "SlotAnnotation",
                "attributes": {
                    "display_text": {"range": "string", "required": True, "alias": "displayText"},
                    "format_text": {"range": "string", "required": True, "alias": "formatText"},
                    "name_type": {"range": "string", "required": False, "alias": "nameType"},
                    "synonym_scope": {"range": "string", "required": False, "alias": "synonymScope"},
                    "synonym_url": {"range": "string", "required": False, "alias": "synonymUrl"}
                }
            },
            
            # Gene-specific name annotations
            "GeneSymbolSlotAnnotation": {
                "description": "Gene symbol annotation",
                "is_a": "NameSlotAnnotation"
            },
            
            "GeneFullNameSlotAnnotation": {
                "description": "Gene full name annotation", 
                "is_a": "NameSlotAnnotation"
            },
            
            "GeneSystematicNameSlotAnnotation": {
                "description": "Gene systematic name annotation",
                "is_a": "NameSlotAnnotation"
            },
            
            "GeneSynonymSlotAnnotation": {
                "description": "Gene synonym annotation",
                "is_a": "NameSlotAnnotation"
            },
            
            # Allele-specific name annotations
            "AlleleSymbolSlotAnnotation": {
                "description": "Allele symbol annotation",
                "is_a": "NameSlotAnnotation"
            },
            
            "AlleleFullNameSlotAnnotation": {
                "description": "Allele full name annotation",
                "is_a": "NameSlotAnnotation" 
            },
            
            "AlleleSynonymSlotAnnotation": {
                "description": "Allele synonym annotation",
                "is_a": "NameSlotAnnotation"
            },
            
            # Ontology terms - standalone
            "OntologyTerm": {
                "description": "Base ontology term",
                "attributes": {
                    "curie": {"range": "string", "required": True, "identifier": True},
                    "name": {"range": "string", "required": False},
                    "definition": {"range": "string", "required": False},
                    "namespace": {"range": "string", "required": False},
                    "obsolete": {"range": "boolean", "required": False}
                }
            },
            
            "NCBITaxonTerm": {
                "description": "NCBI Taxon term",
                "is_a": "OntologyTerm",
                "attributes": {
                    "common_name": {"range": "string", "required": False, "alias": "commonName"},
                    "abbreviation": {"range": "string", "required": False}
                }
            },
            
            "SOTerm": {
                "description": "Sequence Ontology term",
                "is_a": "OntologyTerm"
            },
            
            # Cross reference - standalone
            "CrossReference": {
                "description": "Cross reference to external database",
                "attributes": {
                    "referenced_curie": {"range": "string", "required": True, "alias": "referencedCurie"},
                    "display_name": {"range": "string", "required": False, "alias": "displayName"},
                    "prefix": {"range": "string", "required": False},
                    "page_area": {"range": "string", "required": False, "alias": "pageArea"},
                    "url": {"range": "string", "required": False}
                }
            },
            
            # Data provider - simple
            "DataProvider": {
                "description": "Data provider information", 
                "attributes": {
                    "source_organization": {"range": "string", "required": True, "alias": "sourceOrganization"},
                    "cross_reference": {"range": "CrossReference", "required": False, "alias": "crossReference"}
                }
            },
            
            # Laboratory - simple
            "Laboratory": {
                "description": "Laboratory information",
                "attributes": {
                    "abbreviation": {"range": "string", "required": True},
                    "name": {"range": "string", "required": False},
                    "pi_name": {"range": "string", "required": False, "alias": "piName"},
                    "institution": {"range": "string", "required": False}
                }
            },
            
            # Note - simple  
            "Note": {
                "description": "Note or comment",
                "attributes": {
                    "free_text": {"range": "string", "required": True, "alias": "freeText"},
                    "internal": {"range": "boolean", "required": False}
                }
            }
        }
    }


def test_targeted_generation() -> bool:
    """Test generating from our targeted schema."""
    schema = create_super_minimal_schema()
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(schema, f, default_flow_style=False)
        schema_file = f.name
    
    try:
        print("🧪 Testing targeted schema generation...")
        cmd = ["gen-pydantic", schema_file, "--black"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ SUCCESS! Generated Pydantic models:")
            lines = result.stdout.splitlines()
            print(f"   📊 {len(lines)} lines of code generated")
            
            # Count class definitions
            class_count = len([line for line in lines if line.startswith("class ")])
            print(f"   📦 {class_count} Pydantic classes created")
            
            # Save the output
            output_file = Path("src/agr_curation_api/generated_targeted_models.py")
            output_file.write_text(result.stdout)
            print(f"   💾 Saved to {output_file}")
            
            return True
            
        else:
            print(f"❌ Generation failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        Path(schema_file).unlink(missing_ok=True)


def main():
    """Main function."""
    print("="*70)
    print("CREATING TARGETED PYDANTIC MODELS")
    print("="*70)
    
    print("📋 Target objects:")
    target_objects = [
        "SlotAnnotation", "NameSlotAnnotation", 
        "GeneSymbolSlotAnnotation", "GeneFullNameSlotAnnotation", "GeneSystematicNameSlotAnnotation", "GeneSynonymSlotAnnotation",
        "AlleleSymbolSlotAnnotation", "AlleleFullNameSlotAnnotation", "AlleleSynonymSlotAnnotation",
        "OntologyTerm", "NCBITaxonTerm", "SOTerm",
        "CrossReference", "DataProvider", "Laboratory", "Note"
    ]
    
    for obj in target_objects:
        print(f"   - {obj}")
    
    success = test_targeted_generation()
    
    print("="*70)
    if success:
        print("✅ TARGETED GENERATION SUCCESSFUL!")
        print("🎯 Created simplified models for current API needs")
        print("📝 These models avoid LinkML complexity while providing type safety")
    else:
        print("❌ TARGETED GENERATION FAILED")
    print("="*70)


if __name__ == "__main__":
    main()