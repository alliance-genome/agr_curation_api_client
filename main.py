#!/usr/bin/env python
"""Main script demonstrating AGR Curation API client usage."""

import json
import os
import sys
import time
from datetime import datetime, timedelta

from pydantic import ValidationError

from agr_curation_api import (
    AGRCurationAPIClient,
    APIConfig,
    Gene,
    NCBITaxonTerm,
    OntologyTerm,
    Allele,
    AffectedGenomicModel,
    AGRAPIError
)

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


def display_ncbi_taxon(taxon: NCBITaxonTerm, verbose: bool = False):
    """Display NCBI Taxon term information."""
    # Get taxon name
    taxon_name = taxon.name or taxon.curie or "N/A"

    print(f"\n{'='*60}")
    print(f"NCBI Taxon: {taxon_name}")
    print(f"{'='*60}")

    print(f"CURIE: {taxon.curie or 'N/A'}")
    print(f"Name: {taxon.name or 'N/A'}")

    if taxon.definition:
        # Truncate long definitions unless verbose
        definition = taxon.definition
        if not verbose and len(definition) > 100:
            definition = definition[:97] + "..."
        print(f"Definition: {definition}")

    print(f"Namespace: {taxon.namespace or 'N/A'}")
    print(f"Obsolete: {taxon.obsolete}")

    if verbose:
        print("\nAdditional Details:")
        if hasattr(taxon, 'childCount') and taxon.childCount is not None:
            print(f"  Direct Children: {taxon.childCount}")
        if hasattr(taxon, 'descendantCount') and taxon.descendantCount is not None:
            print(f"  Total Descendants: {taxon.descendantCount}")
        if hasattr(taxon, 'synonyms') and taxon.synonyms:
            print(f"  Synonyms: {', '.join(taxon.synonyms[:5])}")
            if len(taxon.synonyms) > 5:
                print(f"    ... and {len(taxon.synonyms) - 5} more")
        if hasattr(taxon, 'ancestors') and taxon.ancestors:
            print(f"  Ancestors: {', '.join(taxon.ancestors[:5])}")
            if len(taxon.ancestors) > 5:
                print(f"    ... and {len(taxon.ancestors) - 5} more")


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
    """Fetch and display NCBI Taxon terms (species)."""
    print("\n" + "="*70)
    print("FETCHING SPECIES (NCBI TAXON TERMS)")
    print("="*70)

    try:
        response = client.get_species(limit=limit)

        if hasattr(response, 'results'):
            taxon_list = response.results
        else:
            taxon_list = response if isinstance(response, list) else []

        print(f"\nFound {len(taxon_list)} NCBI Taxon term(s)")

        for taxon_data in taxon_list[:limit]:
            try:
                taxon = NCBITaxonTerm(**taxon_data) if isinstance(taxon_data, dict) else taxon_data
                display_ncbi_taxon(taxon, verbose)
            except ValidationError as e:
                print(f"\nError parsing NCBI Taxon data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(taxon_data, indent=2, default=str)}")

        return True
    except AGRAPIError as e:
        print(f"\nError fetching NCBI Taxon terms: {e}")
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


def display_agm(agm: AffectedGenomicModel, verbose: bool = False):
    """Display AGM (Affected Genomic Model) information."""
    # Try to find a meaningful name/identifier
    display_name = 'N/A'
    if agm.agmFullName and agm.agmFullName.displayText:
        display_name = agm.agmFullName.displayText
    elif agm.curie:
        display_name = agm.curie
    elif agm.uniqueId:
        display_name = agm.uniqueId
    elif agm.modEntityId:
        display_name = agm.modEntityId
    
    print(f"\n{'='*60}")
    print(f"AGM: {display_name}")
    print(f"{'='*60}")
    
    if agm.curie:
        print(f"CURIE: {agm.curie}")
    
    if agm.uniqueId:
        print(f"Unique ID: {agm.uniqueId}")
    
    if agm.subtype:
        # Handle subtype which can be a string or dictionary
        if isinstance(agm.subtype, dict):
            subtype_name = agm.subtype.get('name', str(agm.subtype))
        else:
            subtype_name = str(agm.subtype)
        print(f"Subtype: {subtype_name}")
    
    if agm.species:
        if isinstance(agm.species, str):
            print(f"Species: {agm.species}")
        elif hasattr(agm.species, 'displayName'):
            print(f"Species: {agm.species.displayName or agm.species.name}")
        elif isinstance(agm.species, dict):
            species_name = agm.species.get('displayName', agm.species.get('name', 'N/A'))
            print(f"Species: {species_name}")
    
    if agm.dataProvider:
        provider_name = agm.dataProvider.abbreviation if hasattr(agm.dataProvider, 'abbreviation') else str(agm.dataProvider)
        print(f"Data Provider: {provider_name}")
    
    if agm.alleles and len(agm.alleles) > 0:
        print(f"Number of Alleles: {len(agm.alleles)}")
    
    print(f"Obsolete: {agm.obsolete}")
    
    if verbose:
        print("\nAdditional Details:")
        if agm.modEntityId:
            print(f"  MOD Entity ID: {agm.modEntityId}")
        if agm.modInternalId:
            print(f"  MOD Internal ID: {agm.modInternalId}")
        if agm.affectedGenomicModelComponents:
            print(f"  Components: {len(agm.affectedGenomicModelComponents)} component(s)")
        if agm.parentalPopulations:
            print(f"  Parental Populations: {len(agm.parentalPopulations)}")
        if agm.sequenceTargetingReagents:
            print(f"  Sequence Targeting Reagents: {len(agm.sequenceTargetingReagents)}")
        if agm.dateCreated:
            print(f"  Date Created: {agm.dateCreated}")


def fetch_agms(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display AGMs (Affected Genomic Models)."""
    print("\n" + "="*70)
    print("FETCHING AGMS (AFFECTED GENOMIC MODELS)")
    print("="*70)
    
    try:
        response = client.get_agms(limit=limit)
        
        if hasattr(response, 'results'):
            agms = response.results
        else:
            agms = response if isinstance(response, list) else []
        
        print(f"\nFound {len(agms)} AGM(s)")
        
        for agm_data in agms[:limit]:
            try:
                agm = AffectedGenomicModel(**agm_data) if isinstance(agm_data, dict) else agm_data
                display_agm(agm, verbose)
            except ValidationError as e:
                print(f"\nError parsing AGM data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(agm_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching AGMs: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def fetch_fish_models(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display zebrafish AGMs."""
    print("\n" + "="*70)
    print("FETCHING ZEBRAFISH MODELS (ZFIN AGMS)")
    print("="*70)
    
    try:
        response = client.get_fish_models(limit=limit)
        
        if hasattr(response, 'results'):
            fish_models = response.results
        else:
            fish_models = response if isinstance(response, list) else []
        
        print(f"\nFound {len(fish_models)} zebrafish model(s)")
        
        for fish_data in fish_models[:limit]:
            try:
                fish = AffectedGenomicModel(**fish_data) if isinstance(fish_data, dict) else fish_data
                display_agm(fish, verbose)
            except ValidationError as e:
                print(f"\nError parsing zebrafish model data: {e}")
                if verbose:
                    print(f"Raw data: {json.dumps(fish_data, indent=2, default=str)}")
        
        return True
    except AGRAPIError as e:
        print(f"\nError fetching zebrafish models: {e}")
        return False
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return False


def fetch_recently_updated_entities(client: AGRCurationAPIClient, days_back: int = 30, 
                                   limit: int = 5, verbose: bool = False):
    """Fetch entities updated within the specified number of days.
    
    Args:
        client: AGR API client instance
        days_back: Number of days to look back (default: 30)
        limit: Maximum number of results per entity type
        verbose: Show detailed information
    
    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print(f"FETCHING ENTITIES UPDATED IN LAST {days_back} DAYS")
    print("="*70)
    
    # Calculate the date threshold (client will automatically use UTC)
    threshold_date = datetime.now() - timedelta(days=days_back)
    date_str = threshold_date.isoformat()
    
    print(f"Looking for entities updated after: {threshold_date.strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_successful = True
    
    # Fetch recently updated genes
    print(f"\n--- Recently Updated Genes ---")
    try:
        genes = client.get_genes(limit=limit, updated_after=date_str)
        
        if genes:
            print(f"Found {len(genes)} recently updated gene(s)")
            for gene in genes[:3]:  # Show first 3
                if hasattr(gene, 'dbDateUpdated') and gene.dbDateUpdated:
                    print(f"  • {gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'} "
                          f"(Updated: {gene.dbDateUpdated})")
                else:
                    print(f"  • {gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'}")
        else:
            print("No recently updated genes found")
    except Exception as e:
        print(f"Error fetching genes: {e}")
        all_successful = False
    
    # Fetch recently updated alleles
    print(f"\n--- Recently Updated Alleles ---")
    try:
        alleles = client.get_alleles(limit=limit, updated_after=date_str)
        
        if alleles:
            print(f"Found {len(alleles)} recently updated allele(s)")
            for allele in alleles[:3]:  # Show first 3
                if hasattr(allele, 'dbDateUpdated') and allele.dbDateUpdated:
                    print(f"  • {allele.alleleSymbol.displayText if allele.alleleSymbol else allele.curie or 'N/A'} "
                          f"(Updated: {allele.dbDateUpdated})")
                else:
                    print(f"  • {allele.alleleSymbol.displayText if allele.alleleSymbol else allele.curie or 'N/A'}")
        else:
            print("No recently updated alleles found")
    except Exception as e:
        print(f"Error fetching alleles: {e}")
        all_successful = False
    
    # Fetch recently updated Fish Models
    print(f"\n--- Recently Updated Fish Models ---")
    try:
        fish_models = client.get_fish_models(limit=limit, updated_after=date_str)
        
        if fish_models:
            print(f"Found {len(fish_models)} recently updated fish model(s)")
            for agm in fish_models[:3]:  # Show first 3
                display_name = 'N/A'
                if agm.agmFullName and agm.agmFullName.displayText:
                    display_name = agm.agmFullName.displayText
                elif agm.curie:
                    display_name = agm.curie
                elif agm.uniqueId:
                    display_name = agm.uniqueId
                if hasattr(agm, 'dbDateUpdated') and agm.dbDateUpdated:
                    print(f"  • {display_name} (Updated: {agm.dbDateUpdated})")
                else:
                    print(f"  • {display_name}")
        else:
            print("No recently updated fish models found")
    except Exception as e:
        print(f"Error fetching fish models: {e}")
        all_successful = False
    
    # Example with custom date
    print(f"\n--- Custom Date Example ---")
    custom_date = datetime(2024, 1, 1)  # January 1, 2024
    print(f"Fetching genes updated after {custom_date.strftime('%Y-%m-%d')}...")
    
    try:
        genes = client.get_genes(limit=3, updated_after=custom_date)
        if genes:
            print(f"Found {len(genes)} gene(s) updated since {custom_date.strftime('%Y-%m-%d')}")
        else:
            print(f"No genes found updated since {custom_date.strftime('%Y-%m-%d')}")
    except Exception as e:
        print(f"Error: {e}")
        all_successful = False
    
    return all_successful


def fetch_wb_strain_agms(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display AGMs from WB (WormBase) with subtype 'strain'.

    Args:
        client: AGR API client instance
        limit: Maximum number of results to fetch
        verbose: Show detailed information

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("FETCHING WB STRAIN AGMS")
    print("="*70)

    try:
        print("Fetching AGMs from WB with subtype='strain'...")
        wb_strains = client.get_agms(data_provider="WB", subtype="strain", limit=limit)

        if hasattr(wb_strains, 'results'):
            agms = wb_strains.results
        else:
            agms = wb_strains if isinstance(wb_strains, list) else []

        if agms:
            print(f"\n✓ Successfully retrieved {len(agms)} WB strain AGM(s)")

            for agm_data in agms[:limit]:
                try:
                    agm = AffectedGenomicModel(**agm_data) if isinstance(agm_data, dict) else agm_data
                    display_agm(agm, verbose)
                except ValidationError as e:
                    print(f"\nError parsing AGM data: {e}")
                    if verbose:
                        print(f"Raw data: {json.dumps(agm_data, indent=2, default=str)}")
        else:
            print("❌ No WB strain AGMs found")
            return False

        print(f"\n✓ WB strain AGMs fetched successfully!")
        return True

    except AGRAPIError as e:
        print(f"❌ Error fetching WB strain AGMs: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def fetch_wb_transgenes(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Fetch and display transgene alleles from WB (WormBase).

    Args:
        client: AGR API client instance
        limit: Maximum number of results to fetch
        verbose: Show detailed information

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("FETCHING WB TRANSGENES")
    print("="*70)

    try:
        print("Fetching transgene alleles from WB...")
        transgenes = client.get_alleles(data_provider="WB", transgenes_only=True, limit=limit)

        if hasattr(transgenes, 'results'):
            alleles = transgenes.results
        else:
            alleles = transgenes if isinstance(transgenes, list) else []

        if alleles:
            print(f"\n✓ Successfully retrieved {len(alleles)} WB transgene(s)")

            for allele_data in alleles[:limit]:
                try:
                    allele = Allele(**allele_data) if isinstance(allele_data, dict) else allele_data
                    print(f"\n{'='*60}")
                    print(f"Transgene: {allele.curie or 'N/A'}")
                    print(f"{'='*60}")

                    if allele.alleleSymbol:
                        print(f"Symbol: {allele.alleleSymbol.displayText}")

                    if allele.alleleFullName:
                        print(f"Full Name: {allele.alleleFullName.displayText}")

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
                        if allele.dateCreated:
                            print(f"  Date Created: {allele.dateCreated}")

                except ValidationError as e:
                    print(f"\nError parsing transgene data: {e}")
                    if verbose:
                        print(f"Raw data: {json.dumps(allele_data, indent=2, default=str)}")
        else:
            print("❌ No WB transgenes found")
            return False

        print(f"\n✓ WB transgenes fetched successfully!")
        return True

    except AGRAPIError as e:
        print(f"❌ Error fetching WB transgenes: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_wb_data_provider(client: AGRCurationAPIClient, limit: int = 5):
    """Test fetching genes from WB data provider to verify searchFilters format.

    Args:
        client: AGR API client instance
        limit: Maximum number of results to fetch

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("TESTING WB DATA PROVIDER FILTERING")
    print("="*70)

    try:
        print("Fetching genes from WB (WormBase) data provider...")
        wb_genes = client.get_genes(data_provider="WB", limit=limit)

        if wb_genes:
            print(f"✓ Successfully retrieved {len(wb_genes)} WB gene(s)")
            for i, gene in enumerate(wb_genes[:3], 1):  # Show first 3
                symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
                data_provider = getattr(gene.dataProvider, 'abbreviation', 'N/A') if gene.dataProvider else 'N/A'
                print(f"  {i}. {symbol} (Provider: {data_provider})")
        else:
            print("❌ No WB genes found")
            return False

        # Test with a different data provider for comparison
        print(f"\nTesting MGI data provider for comparison...")
        mgi_genes = client.get_genes(data_provider="MGI", limit=limit)

        if mgi_genes:
            print(f"✓ Successfully retrieved {len(mgi_genes)} MGI gene(s)")
            for i, gene in enumerate(mgi_genes[:3], 1):  # Show first 3
                symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
                data_provider = getattr(gene.dataProvider, 'abbreviation', 'N/A') if gene.dataProvider else 'N/A'
                print(f"  {i}. {symbol} (Provider: {data_provider})")
        else:
            print("❌ No MGI genes found")

        print(f"\n✓ Data provider filtering test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error testing WB data provider: {e}")
        return False


def test_graphql_genes(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Test GraphQL gene queries with different field selections.

    Args:
        client: AGR API client instance
        limit: Maximum number of results to fetch
        verbose: Show detailed information

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("TESTING GRAPHQL GENE QUERIES")
    print("="*70)

    all_successful = True

    # Test 1: Get genes with minimal fields
    print("\n--- Test 1: Minimal Fields (C. elegans genes) ---")
    try:
        genes = client.get_genes_graphql(
            fields="minimal",
            taxon="NCBITaxon:6239",
            limit=limit
        )
        print(f"✓ Found {len(genes)} genes with minimal fields")
        for gene in genes[:3]:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol}")
    except Exception as e:
        print(f"❌ Error: {e}")
        all_successful = False

    # Test 2: Get genes with standard fields
    print("\n--- Test 2: Standard Fields (WB data provider) ---")
    try:
        genes = client.get_genes_graphql(
            fields="standard",
            data_provider="WB",
            limit=limit
        )
        print(f"✓ Found {len(genes)} genes with standard fields")
        for gene in genes[:2]:
            print(f"\n  Gene: {gene.primaryExternalId}")
            if gene.geneSymbol:
                print(f"    Symbol: {gene.geneSymbol.displayText}")
            if gene.geneFullName:
                print(f"    Full Name: {gene.geneFullName.displayText}")
    except Exception as e:
        print(f"❌ Error: {e}")
        all_successful = False

    # Test 3: Get genes with custom field list
    print("\n--- Test 3: Custom Field List ---")
    try:
        genes = client.get_genes_graphql(
            fields=["primaryExternalId", "geneSymbol", "geneFullName"],
            data_provider="WB",
            limit=3
        )
        print(f"✓ Found {len(genes)} genes with custom fields")
        for gene in genes:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol}")
    except Exception as e:
        print(f"❌ Error: {e}")
        all_successful = False

    # Test 4: Get single gene by ID
    print("\n--- Test 4: Get Single Gene by ID ---")
    try:
        genes = client.get_genes_graphql(data_provider="WB", limit=1)
        if genes:
            gene_id = genes[0].primaryExternalId
            print(f"Fetching gene: {gene_id}")
            gene = client.get_gene_graphql(gene_id, fields="basic")
            if gene:
                print(f"  ✓ Found: {gene.primaryExternalId}")
                if gene.geneSymbol:
                    print(f"    Symbol: {gene.geneSymbol.displayText}")
        else:
            print("  ⚠️ No genes available to test single gene fetch")
    except Exception as e:
        print(f"❌ Error: {e}")
        all_successful = False

    if all_successful:
        print("\n✓ All GraphQL gene tests completed successfully!")
    else:
        print("\n⚠️ Some GraphQL gene tests failed")

    return all_successful


def test_graphql_alleles(client: AGRCurationAPIClient, limit: int = 5, verbose: bool = False):
    """Test GraphQL allele queries.

    Args:
        client: AGR API client instance
        limit: Maximum number of results to fetch
        verbose: Show detailed information

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("TESTING GRAPHQL ALLELE QUERIES")
    print("="*70)

    try:
        # Test: Get alleles with default fields
        print("\n--- Test: Alleles from WB ---")
        alleles = client.get_alleles_graphql(
            data_provider="WB",
            limit=limit
        )
        print(f"✓ Found {len(alleles)} alleles via GraphQL")
        for allele in alleles[:3]:
            symbol = allele.alleleSymbol.displayText if allele.alleleSymbol else 'N/A'
            print(f"  - {allele.primaryExternalId}: {symbol}")

        print("\n✓ GraphQL allele tests completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def benchmark_all_data_sources(limit: int = 100, runs: int = 3):
    """Benchmark REST API vs GraphQL vs Database with different field sets.

    Args:
        limit: Number of records to fetch per test
        runs: Number of times to run each test for averaging

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("PERFORMANCE BENCHMARK: REST API vs GraphQL vs Database")
    print("="*70)
    print(f"Configuration: {limit} records, {runs} runs per test")
    print(f"Testing with WB (WormBase) genes")
    print(f"Note: REST API uses data_provider='WB', GraphQL/DB use taxon='NCBITaxon:6239'")

    results = {}
    db_available = True

    # Create clients for each data source
    api_client = AGRCurationAPIClient(data_source="api")
    graphql_client = AGRCurationAPIClient(data_source="graphql")

    # Try to create database client and test it
    try:
        db_client = AGRCurationAPIClient(data_source="db")
        # Test if database is actually accessible by trying a minimal query
        print("\nTesting database connectivity...")
        test_genes = db_client.get_genes(taxon="NCBITaxon:6239", limit=1)
        if not test_genes:
            print("⚠️  Database returned no results - may not be configured correctly")
            print("   Skipping database tests\n")
            db_available = False
            db_client = None
        else:
            print("✓ Database connection successful\n")
    except Exception as e:
        print(f"⚠️  Database client not available: {e}")
        print("   Skipping database tests\n")
        db_available = False
        db_client = None

    try:
        # Test 1: REST API (all fields) - uses data_provider since REST API doesn't support taxon filtering
        print("\n--- Test 1: REST API (all fields, WB genes) ---")
        rest_times = []
        for run in range(runs):
            start = time.time()
            genes = api_client.get_genes(data_provider="WB", limit=limit)
            elapsed = time.time() - start
            rest_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        rest_avg = sum(rest_times) / len(rest_times)
        results['REST API (all fields)'] = rest_avg
        print(f"  Average: {rest_avg:.3f}s")

        # Test 2: GraphQL with minimal fields
        print("\n--- Test 2: GraphQL (minimal fields) ---")
        minimal_times = []
        for run in range(runs):
            start = time.time()
            genes = graphql_client.get_genes(
                taxon="NCBITaxon:6239",
                limit=limit,
                fields="minimal"
            )
            elapsed = time.time() - start
            minimal_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        minimal_avg = sum(minimal_times) / len(minimal_times)
        results['GraphQL (minimal)'] = minimal_avg
        print(f"  Average: {minimal_avg:.3f}s")

        # Test 3: GraphQL with basic fields
        print("\n--- Test 3: GraphQL (basic fields) ---")
        basic_times = []
        for run in range(runs):
            start = time.time()
            genes = graphql_client.get_genes(
                taxon="NCBITaxon:6239",
                limit=limit,
                fields="basic"
            )
            elapsed = time.time() - start
            basic_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        basic_avg = sum(basic_times) / len(basic_times)
        results['GraphQL (basic)'] = basic_avg
        print(f"  Average: {basic_avg:.3f}s")

        # Test 4: GraphQL with standard fields
        print("\n--- Test 4: GraphQL (standard fields) ---")
        standard_times = []
        for run in range(runs):
            start = time.time()
            genes = graphql_client.get_genes(
                taxon="NCBITaxon:6239",
                limit=limit,
                fields="standard"
            )
            elapsed = time.time() - start
            standard_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        standard_avg = sum(standard_times) / len(standard_times)
        results['GraphQL (standard)'] = standard_avg
        print(f"  Average: {standard_avg:.3f}s")

        # Test 5: GraphQL with full fields
        print("\n--- Test 5: GraphQL (full fields) ---")
        full_times = []
        for run in range(runs):
            start = time.time()
            genes = graphql_client.get_genes(
                taxon="NCBITaxon:6239",
                limit=limit,
                fields="full"
            )
            elapsed = time.time() - start
            full_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        full_avg = sum(full_times) / len(full_times)
        results['GraphQL (full)'] = full_avg
        print(f"  Average: {full_avg:.3f}s")

        # Test 6: Database (direct SQL) - equivalent to minimal fields
        if db_available and db_client:
            print("\n--- Test 6: Database (direct SQL, minimal fields) ---")
            print("      Note: DB returns only ID + symbol (same as GraphQL minimal)")
            db_times = []
            for run in range(runs):
                start = time.time()
                genes = db_client.get_genes(taxon="NCBITaxon:6239", limit=limit)
                elapsed = time.time() - start
                db_times.append(elapsed)
                print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

            db_avg = sum(db_times) / len(db_times)
            results['Database (SQL minimal)'] = db_avg
            print(f"  Average: {db_avg:.3f}s")

        # Summary table
        print("\n" + "="*70)
        print("PERFORMANCE SUMMARY")
        print("="*70)
        print(f"{'Method':<30} {'Avg Time (s)':<15} {'vs REST':<15} {'Speedup':<15}")
        print("-"*70)

        rest_baseline = results['REST API (all fields)']
        for method, avg_time in results.items():
            diff = avg_time - rest_baseline
            diff_pct = ((avg_time - rest_baseline) / rest_baseline) * 100
            speedup = rest_baseline / avg_time if avg_time > 0 else 0

            if method == 'REST API (all fields)':
                print(f"{method:<30} {avg_time:>8.3f}s       {'(baseline)':<15} {'-':<15}")
            else:
                sign = '+' if diff > 0 else ''
                print(f"{method:<30} {avg_time:>8.3f}s       {sign}{diff_pct:>5.1f}%          {speedup:.2f}x")

        print("\n" + "="*70)

        # Analysis
        best_method = min(results.items(), key=lambda x: x[1])
        print(f"\n🏆 Best performance: {best_method[0]} ({best_method[1]:.3f}s average)")

        if best_method[1] < rest_baseline:
            improvement = ((rest_baseline - best_method[1]) / rest_baseline) * 100
            print(f"   {improvement:.1f}% faster than REST API")

        print("\n💡 Recommendations:")
        print("   - Use 'minimal' fields for listings and searches")
        print("   - Use 'basic' or 'standard' for display pages")
        print("   - Use 'full' only when all fields are needed")
        print("   - GraphQL allows requesting exactly what you need, reducing data transfer")
        if db_available:
            print("   - Database access returns minimal fields (ID + symbol) for maximum speed")
            print("   - Compare Database vs GraphQL (minimal) for apples-to-apples comparison")
            print("   - Use Database for bulk operations when you only need basic identifiers")
        else:
            print("   - Database access requires proper credentials (not available in this test)")

        print("\n✓ Performance benchmark completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Error during benchmark: {e}")
        import traceback
        traceback.print_exc()
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

    success = fetch_agms(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    success = fetch_fish_models(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success
    
    # Demonstrate date filtering functionality
    success = fetch_recently_updated_entities(client, days_back=30, limit=LIMIT, verbose=False)
    all_successful = all_successful and success
    
    # Test WB data provider filtering
    success = test_wb_data_provider(client, limit=LIMIT)
    all_successful = all_successful and success
    
    # Fetch WB strain AGMs
    success = fetch_wb_strain_agms(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    # Fetch WB transgenes
    success = fetch_wb_transgenes(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    # Test GraphQL API
    success = test_graphql_genes(client, limit=LIMIT, verbose=True)
    all_successful = all_successful and success

    success = test_graphql_alleles(client, limit=LIMIT, verbose=True)
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
