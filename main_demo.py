#!/usr/bin/env python
"""Demonstration script showcasing all three data access methods in AGR Curation API client.

This script demonstrates:
1. REST API access (default)
2. GraphQL API access (efficient field selection)
3. Direct database access (high-performance bulk queries)
"""

import sys
import time
from agr_curation_api import AGRCurationAPIClient, DataSource, AGRAPIError

sys.path.insert(0, 'src')


def demo_rest_api():
    """Demonstrate REST API access (default behavior)."""
    print("\n" + "="*70)
    print("DEMONSTRATION 1: REST API ACCESS")
    print("="*70)
    print("Using the traditional REST API endpoints (default behavior)")

    try:
        # Create client with REST API (default)
        client = AGRCurationAPIClient()
        print("✓ Client created with data_source='api' (default)")

        # Fetch genes using REST API
        print("\n--- Fetching WB genes via REST API ---")
        genes = client.get_genes(data_provider="WB", limit=5)
        print(f"✓ Retrieved {len(genes)} genes")
        for gene in genes[:3]:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol}")

        # Fetch alleles using REST API
        print("\n--- Fetching WB alleles via REST API ---")
        alleles = client.get_alleles(data_provider="WB", limit=5)
        print(f"✓ Retrieved {len(alleles)} alleles")
        for allele in alleles[:3]:
            symbol = allele.alleleSymbol.displayText if allele.alleleSymbol else 'N/A'
            print(f"  - {allele.primaryExternalId}: {symbol}")

        print("\n✓ REST API demonstration completed successfully!")
        return True

    except AGRAPIError as e:
        print(f"✗ Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def demo_graphql_api():
    """Demonstrate GraphQL API access with flexible field selection."""
    print("\n" + "="*70)
    print("DEMONSTRATION 2: GRAPHQL API ACCESS")
    print("="*70)
    print("Using GraphQL for efficient queries with custom field selection")

    try:
        # Create client with GraphQL as primary data source
        client = AGRCurationAPIClient(data_source="graphql")
        print("✓ Client created with data_source='graphql'")

        # Example 1: Minimal fields (most efficient)
        print("\n--- Example 1: Minimal fields (C. elegans genes) ---")
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=5, fields="minimal")
        print(f"✓ Retrieved {len(genes)} genes with minimal fields")
        for gene in genes[:3]:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol}")

        # Example 2: Standard fields (balanced)
        print("\n--- Example 2: Standard fields (WB genes) ---")
        genes = client.get_genes(data_provider="WB", limit=5, fields="standard")
        print(f"✓ Retrieved {len(genes)} genes with standard fields")
        for gene in genes[:2]:
            print(f"\n  Gene: {gene.primaryExternalId}")
            if gene.geneSymbol:
                print(f"    Symbol: {gene.geneSymbol.displayText}")
            if gene.geneFullName:
                print(f"    Full Name: {gene.geneFullName.displayText}")
            if gene.geneType:
                type_name = gene.geneType.name if hasattr(gene.geneType, 'name') else str(gene.geneType)
                print(f"    Type: {type_name}")

        # Example 3: Custom field list (exactly what you need)
        print("\n--- Example 3: Custom field list ---")
        genes = client.get_genes(
            data_provider="WB",
            limit=3,
            fields=["primaryExternalId", "geneSymbol", "taxon"]
        )
        print(f"✓ Retrieved {len(genes)} genes with custom fields")
        for gene in genes:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            taxon = gene.taxon.name if hasattr(gene.taxon, 'name') else str(gene.taxon) if gene.taxon else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol} ({taxon})")

        # Example 4: GraphQL alleles
        print("\n--- Example 4: GraphQL alleles from WB ---")
        alleles = client.get_alleles(data_provider="WB", limit=5)
        print(f"✓ Retrieved {len(alleles)} alleles")
        for allele in alleles[:3]:
            symbol = allele.alleleSymbol.displayText if allele.alleleSymbol else 'N/A'
            print(f"  - {allele.primaryExternalId}: {symbol}")

        print("\n✓ GraphQL API demonstration completed successfully!")
        return True

    except AGRAPIError as e:
        print(f"✗ Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def demo_database_access():
    """Demonstrate direct database access for high-performance queries."""
    print("\n" + "="*70)
    print("DEMONSTRATION 3: DIRECT DATABASE ACCESS")
    print("="*70)
    print("Using direct SQL queries for high-performance bulk operations")
    print("NOTE: Requires database credentials in environment variables")

    try:
        # Create client with database as primary data source
        client = AGRCurationAPIClient(data_source="db")
        print("✓ Client created with data_source='db'")

        # Example 1: Get genes by taxon (most common use case)
        print("\n--- Example 1: C. elegans genes from database ---")
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=10)
        print(f"✓ Retrieved {len(genes)} genes from database")
        for gene in genes[:5]:
            symbol = gene.geneSymbol.displayText if gene.geneSymbol else 'N/A'
            print(f"  - {gene.primaryExternalId}: {symbol}")

        # Example 2: Get alleles by taxon
        print("\n--- Example 2: C. elegans alleles from database ---")
        alleles = client.get_alleles(taxon="NCBITaxon:6239", limit=10)
        print(f"✓ Retrieved {len(alleles)} alleles from database")
        for allele in alleles[:5]:
            symbol = allele.alleleSymbol.displayText if allele.alleleSymbol else 'N/A'
            print(f"  - {allele.primaryExternalId}: {symbol}")

        # Example 3: Get alleles by data provider
        print("\n--- Example 3: WB alleles by data provider ---")
        alleles = client.get_alleles(data_provider="WB", limit=10)
        print(f"✓ Retrieved {len(alleles)} alleles from database")
        for allele in alleles[:5]:
            symbol = allele.alleleSymbol.displayText if allele.alleleSymbol else 'N/A'
            print(f"  - {allele.primaryExternalId}: {symbol}")

        print("\n✓ Database access demonstration completed successfully!")
        return True

    except AGRAPIError as e:
        print(f"✗ Error: {e}")
        print("  (This is expected if database credentials are not configured)")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        print("  (This is expected if database credentials are not configured)")
        return False


def demo_per_call_override():
    """Demonstrate overriding data source on a per-call basis."""
    print("\n" + "="*70)
    print("DEMONSTRATION 4: PER-CALL DATA SOURCE OVERRIDE")
    print("="*70)
    print("Mixing data sources within a single client instance")

    try:
        # Create client with REST API as default
        client = AGRCurationAPIClient(data_source="api")
        print("✓ Client created with data_source='api' (REST as default)")

        # Call 1: Use default (REST API)
        print("\n--- Call 1: Using default (REST API) ---")
        genes = client.get_genes(data_provider="WB", limit=3)
        print(f"✓ Retrieved {len(genes)} genes via REST API")

        # Call 2: Override to use GraphQL for this call only
        print("\n--- Call 2: Override to GraphQL for this call ---")
        genes = client.get_genes(
            data_provider="WB",
            limit=3,
            fields="minimal",
            data_source="graphql"
        )
        print(f"✓ Retrieved {len(genes)} genes via GraphQL")

        # Call 3: Back to default (REST API)
        print("\n--- Call 3: Back to default (REST API) ---")
        alleles = client.get_alleles(data_provider="WB", limit=3)
        print(f"✓ Retrieved {len(alleles)} alleles via REST API")

        print("\n✓ Per-call override demonstration completed successfully!")
        return True

    except AGRAPIError as e:
        print(f"✗ Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def demo_performance_comparison():
    """Compare performance of different data access methods."""
    print("\n" + "="*70)
    print("DEMONSTRATION 5: PERFORMANCE COMPARISON")
    print("="*70)
    print("Comparing execution times for different data sources")
    print("(Fetching 50 WB genes with each method)")

    results = {}

    # Test REST API
    print("\n--- Test 1: REST API ---")
    try:
        client = AGRCurationAPIClient(data_source="api")
        start = time.time()
        genes = client.get_genes(data_provider="WB", limit=50)
        elapsed = time.time() - start
        results['REST API'] = elapsed
        print(f"✓ Retrieved {len(genes)} genes in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Error: {e}")
        results['REST API'] = None

    # Test GraphQL with minimal fields
    print("\n--- Test 2: GraphQL (minimal fields) ---")
    try:
        client = AGRCurationAPIClient(data_source="graphql")
        start = time.time()
        genes = client.get_genes(data_provider="WB", limit=50, fields="minimal")
        elapsed = time.time() - start
        results['GraphQL (minimal)'] = elapsed
        print(f"✓ Retrieved {len(genes)} genes in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Error: {e}")
        results['GraphQL (minimal)'] = None

    # Test GraphQL with standard fields
    print("\n--- Test 3: GraphQL (standard fields) ---")
    try:
        client = AGRCurationAPIClient(data_source="graphql")
        start = time.time()
        genes = client.get_genes(data_provider="WB", limit=50, fields="standard")
        elapsed = time.time() - start
        results['GraphQL (standard)'] = elapsed
        print(f"✓ Retrieved {len(genes)} genes in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Error: {e}")
        results['GraphQL (standard)'] = None

    # Test Database access
    print("\n--- Test 4: Database (direct SQL) ---")
    try:
        client = AGRCurationAPIClient(data_source="db")
        start = time.time()
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=50)
        elapsed = time.time() - start
        results['Database'] = elapsed
        print(f"✓ Retrieved {len(genes)} genes in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("  (Skipped - database credentials not configured)")
        results['Database'] = None

    # Summary
    print("\n" + "="*70)
    print("PERFORMANCE SUMMARY")
    print("="*70)
    if any(v is not None for v in results.values()):
        valid_results = {k: v for k, v in results.items() if v is not None}
        if valid_results:
            fastest = min(valid_results.items(), key=lambda x: x[1])
            for method, time_taken in results.items():
                if time_taken is not None:
                    status = "🏆 FASTEST" if method == fastest[0] else ""
                    print(f"{method:<25} {time_taken:>8.3f}s  {status}")
                else:
                    print(f"{method:<25} {'N/A':>8}  (skipped)")

            print("\n💡 Key Takeaways:")
            print("   - GraphQL with minimal fields is typically fastest for small result sets")
            print("   - Database access is best for bulk operations (when available)")
            print("   - REST API provides all fields but may be slower for large datasets")
            print("   - Choose the right tool for your use case!")
        return True
    else:
        print("No valid results to compare")
        return False


def main():
    """Run all demonstrations."""
    print("="*70)
    print("AGR CURATION API CLIENT - MODULAR ARCHITECTURE DEMONSTRATION")
    print("="*70)
    print("This script demonstrates the three data access methods:")
    print("  1. REST API (traditional, full-featured)")
    print("  2. GraphQL (efficient, flexible field selection)")
    print("  3. Database (high-performance, direct SQL queries)")
    print("="*70)

    all_successful = True

    # Run demonstrations
    all_successful = demo_rest_api() and all_successful
    all_successful = demo_graphql_api() and all_successful
    all_successful = demo_database_access() and all_successful
    all_successful = demo_per_call_override() and all_successful
    all_successful = demo_performance_comparison() and all_successful

    # Final summary
    print("\n" + "="*70)
    print("FINAL SUMMARY")
    print("="*70)

    if all_successful:
        print("✅ All demonstrations completed successfully!")
    else:
        print("⚠️  Some demonstrations failed or were skipped")
        print("    (Database access requires proper credentials)")

    print("\n📚 Documentation:")
    print("   - See CLAUDE.md for setup instructions")
    print("   - Check src/agr_curation_api/ for module documentation")

    print("\n🎯 Usage Examples:")
    print("   # REST API (default)")
    print("   client = AGRCurationAPIClient()")
    print("   genes = client.get_genes(data_provider='WB', limit=10)")
    print()
    print("   # GraphQL for efficient queries")
    print("   client = AGRCurationAPIClient(data_source='graphql')")
    print("   genes = client.get_genes(taxon='NCBITaxon:6239', fields='minimal')")
    print()
    print("   # Database for bulk operations")
    print("   client = AGRCurationAPIClient(data_source='db')")
    print("   genes = client.get_genes(taxon='NCBITaxon:6239', limit=1000)")

    print("\n" + "="*70)

    return 0 if all_successful else 1


if __name__ == "__main__":
    sys.exit(main())