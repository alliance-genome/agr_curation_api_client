#!/usr/bin/env python
"""Main script demonstrating AGR Curation API client usage."""

import json
import os
import sys

from pydantic import ValidationError

from agr_curation_api import AGRCurationAPIClient, APIConfig, Gene, Species, OntologyTerm, Allele, AGRAPIError

LIMIT = 10

sys.path.insert(0, 'src')


def display_gene(gene, verbose: bool = False):
    """Display gene information."""
    symbol_text = gene.geneSymbol.displayText if gene.geneSymbol else "N/A"
    
    print(f"\n{'='*60}")
    print(f"Gene: {symbol_text}")
    print(f"{'='*60}")
    
    if gene.geneSymbol:
        print(f"Symbol: {symbol_text}")

    if gene.taxon:
        if hasattr(gene.taxon, 'name'):
            taxon_name = gene.taxon.name
        elif isinstance(gene.taxon, str):
            taxon_name = gene.taxon
        else:
            taxon_name = gene.taxon.get('name', gene.taxon.get('curie', 'N/A'))
        print(f"Taxon: {taxon_name}")
    
    if gene.geneType:
        if hasattr(gene.geneType, 'name'):
            type_name = gene.geneType.name
        elif isinstance(gene.geneType, str):
            type_name = gene.geneType
        else:
            type_name = gene.geneType.get('name', gene.geneType.get('curie', 'N/A'))
        print(f"Type: {type_name}")
    
    print(f"Obsolete: {gene.obsolete}")
    
    if verbose:
        print("\nAdditional Details:")
        if gene.geneSystematicName:
            print(f"  Systematic Name: {gene.geneSystematicName.displayText}")
            
        if gene.geneSecondaryIds:
            secondary_ids = []
            for id_obj in gene.geneSecondaryIds:
                if hasattr(id_obj, 'secondaryId'):
                    secondary_ids.append(id_obj.secondaryId)
                elif isinstance(id_obj, str):
                    secondary_ids.append(id_obj)
            if secondary_ids:
                print(f"  Secondary IDs: {', '.join(secondary_ids)}")
                
        if gene.createdBy:
            if isinstance(gene.createdBy, str):
                print(f"  Created By: {gene.createdBy}")
            elif hasattr(gene.createdBy, 'uniqueId'):
                print(f"  Created By: {gene.createdBy.uniqueId}")
        if gene.dateCreated:
            print(f"  Date Created: {gene.dateCreated}")


def display_species(species: Species, verbose: bool = False):
    """Display species information."""
    # Get species name from various sources
    species_name = "N/A"
    
    # Try different name fields
    if hasattr(species, 'displayName') and species.displayName:
        species_name = species.displayName
    elif hasattr(species, 'name') and species.name:
        species_name = species.name
    elif hasattr(species, 'curie') and species.curie:
        species_name = species.curie
    elif species.taxon:
        if hasattr(species.taxon, 'name') and species.taxon.name:
            species_name = species.taxon.name
        elif isinstance(species.taxon, dict) and 'name' in species.taxon:
            species_name = species.taxon['name']
    
    print(f"\n{'='*60}")
    print(f"Species: {species_name}")
    print(f"{'='*60}")
    
    print(f"Abbreviation: {getattr(species, 'abbreviation', None) or 'N/A'}")
    print(f"Display Name: {getattr(species, 'displayName', None) or 'N/A'}")
    print(f"CURIE: {getattr(species, 'curie', None) or 'N/A'}")
    
    if verbose:
        print("\nDebug - Model data:")
        data = species.model_dump()
        for key, value in data.items():
            if value is not None:
                print(f"  {key}: {value}")
    
    if hasattr(species, 'genomeAssembly') and species.genomeAssembly:
        print(f"Genome Assembly: {species.genomeAssembly}")
    
    if hasattr(species, 'phylogeneticOrder') and species.phylogeneticOrder is not None:
        print(f"Phylogenetic Order: {species.phylogeneticOrder}")
    
    if verbose and hasattr(species, 'commonNames') and species.commonNames:
        print(f"Common Names: {', '.join(species.commonNames)}")


def display_ontology_term(term: OntologyTerm, verbose: bool = False):
    """Display ontology term information."""
    print(f"\n{'='*60}")
    print(f"Ontology Term: {term.curie}")
    print(f"{'='*60}")
    
    print(f"Name: {term.name or 'N/A'}")
    
    if term.definition:
        # Truncate long definitions unless verbose
        definition = term.definition
        if not verbose and len(definition) > 100:
            definition = definition[:97] + "..."
        print(f"Definition: {definition}")
    
    print(f"Namespace: {term.namespace or 'N/A'}")
    print(f"Obsolete: {term.obsolete}")
    
    if verbose:
        print("\nAdditional Details:")
        if hasattr(term, 'childCount') and term.childCount is not None:
            print(f"  Direct Children: {term.childCount}")
        if hasattr(term, 'descendantCount') and term.descendantCount is not None:
            print(f"  Total Descendants: {term.descendantCount}")
        if hasattr(term, 'ancestors') and term.ancestors:
            print(f"  Ancestors: {', '.join(term.ancestors[:5])}")
            if len(term.ancestors) > 5:
                print(f"    ... and {len(term.ancestors) - 5} more")


def display_allele(allele: Allele, verbose: bool = False):
    """Display allele information."""
    print(f"\n{'='*60}")
    print(f"Allele: {allele.curie or 'N/A'}")
    print(f"{'='*60}")
    
    if allele.alleleSymbol:
        print(f"Symbol: {allele.alleleSymbol.displayText}")
    
    if allele.alleleFullName:
        print(f"Full Name: {allele.alleleFullName.displayText}")
    
    if allele.taxon:
        if hasattr(allele.taxon, 'name'):
            taxon_name = allele.taxon.name
        elif isinstance(allele.taxon, dict):
            taxon_name = allele.taxon.get('name', allele.taxon.get('curie', 'N/A'))
        else:
            taxon_name = str(allele.taxon)
        print(f"Taxon: {taxon_name}")
    
    print(f"Obsolete: {allele.obsolete}")
    
    if allele.isExtinct is not None:
        print(f"Extinct: {allele.isExtinct}")
    
    if verbose:
        print("\nAdditional Details:")
        if allele.laboratoryOfOrigin:
            if hasattr(allele.laboratoryOfOrigin, 'name'):
                lab_name = allele.laboratoryOfOrigin.name or allele.laboratoryOfOrigin.abbreviation
            else:
                lab_name = str(allele.laboratoryOfOrigin)
            print(f"  Lab of Origin: {lab_name}")
            
        if allele.isExtrachromosomal is not None:
            print(f"  Extrachromosomal: {allele.isExtrachromosomal}")
        if allele.isIntegrated is not None:
            print(f"  Integrated: {allele.isIntegrated}")
        if allele.references:
            print(f"  References: {len(allele.references)} publication(s)")


def fetch_genes(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display genes."""
    print("\n" + "="*70)
    print("FETCHING GENES")
    print("="*70)
    
    try:
        response = client.get_genes(limit=limit)
        
        if hasattr(response, 'results'):
            genes = response.results
        else:
            genes = response if isinstance(response, list) else []
        
        print(f"\nFound {len(genes)} gene(s)")
        
        for gene_data in genes[:limit]:
            try:
                gene = Gene(**gene_data) if isinstance(gene_data, dict) else gene_data
                display_gene(gene, verbose)
            except ValidationError as e:
                print(f"\nError parsing gene data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(gene_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching genes: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def fetch_species(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display species."""
    print("\n" + "="*70)
    print("FETCHING SPECIES")
    print("="*70)
    
    try:
        response = client.get_species(limit=limit)
        
        if hasattr(response, 'results'):
            species_list = response.results
        else:
            species_list = response if isinstance(response, list) else []
        
        print(f"\nFound {len(species_list)} species")
        
        for species_data in species_list[:limit]:
            try:
                species = Species(**species_data) if isinstance(species_data, dict) else species_data
                display_species(species, verbose)
            except ValidationError as e:
                print(f"\nError parsing species data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(species_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching species: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def fetch_ontology_terms(client: AGRCurationAPIClient, namespace: str = "GO",
                         limit: int = 5, verbose: bool = False):
    """Fetch and display ontology terms."""
    print("\n" + "="*70)
    print(f"FETCHING {namespace} ONTOLOGY TERMS")
    print("="*70)
    
    try:
        # Try to fetch ontology terms - adjust endpoint as needed
        roots = client.get_ontology_root_nodes(node_type="goterm")
        children = []
        for root in roots:
            children = client.get_ontology_node_children(node_curie=root.curie, node_type="goterm")
            break

        print(f"\nFound {len(roots)} root nodes")
        print(f"\nFound {len(children)} first level children")
        
        for term_data in roots:
            try:
                term = OntologyTerm(**term_data) if isinstance(term_data, dict) else term_data
                display_ontology_term(term, verbose)
            except ValidationError as e:
                print(f"\nError parsing ontology term data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(term_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching ontology terms: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def fetch_alleles(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display alleles."""
    print("\n" + "="*70)
    print("FETCHING ALLELES")
    print("="*70)
    
    try:
        response = client.get_alleles(limit=limit)
        
        if hasattr(response, 'results'):
            alleles = response.results
        else:
            alleles = response if isinstance(response, list) else []
        
        print(f"\nFound {len(alleles)} allele(s)")
        
        for allele_data in alleles[:limit]:
            try:
                allele = Allele(**allele_data) if isinstance(allele_data, dict) else allele_data
                display_allele(allele, verbose)
            except ValidationError as e:
                print(f"\nError parsing allele data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(allele_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching alleles: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def main():
    # Print header
    print("="*70)
    print("AGR CURATION API CLIENT DEMONSTRATION")
    print("="*70)
    print(f"Base URL: {os.getenv('AGR_API_BASE_URL', 'https://api.alliancegenome.org')}")
    print(f"Fetching: all entities")
    print(f"Limit: 10 items per type")
    
    # Setup client
    try:
        config = APIConfig()
        client = AGRCurationAPIClient(config)
        print("\n✓ Client initialized successfully")
    except Exception as e:
        print(f"\n✗ Failed to initialize client: {e}")
        return 1
    
    # Track success
    all_successful = True
    
    # Fetch data based on entity type
    success = fetch_genes(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    success = fetch_species(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    success = fetch_ontology_terms(client, namespace="GO", limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    success = fetch_alleles(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if all_successful:
        print("✅ All API calls completed successfully!")
    else:
        print("⚠️  Some API calls failed. Check the output above for details.")
        print("\nTip: If authentication failed, set your OKTA_TOKEN environment variable:")
        print("  export OKTA_TOKEN='your-token-here'")
    
    print("="*70)
    
    return 0 if all_successful else 1


if __name__ == "__main__":
    sys.exit(main())
