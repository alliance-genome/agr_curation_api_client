#!/usr/bin/env python
"""Benchmark script to compare REST API vs GraphQL vs Database performance."""

import sys
import time
from typing import List
from agr_curation_api import AGRCurationAPIClient, APIConfig
from agr_curation_api.models import Gene


sys.path.insert(0, 'src')


def fetch_all_genes_paginated(client: AGRCurationAPIClient, page_size: int = 1000) -> List[Gene]:
    """Fetch all genes using pagination.

    Args:
        client: API client instance
        page_size: Number of records per page

    Returns:
        List of all genes
    """
    all_genes = []
    page = 0

    while True:
        genes = client.get_genes(data_provider="WB", limit=page_size, page=page, include_obsolete=False)
        if not genes:
            break
        all_genes.extend(genes)
        page += 1

    return all_genes


def fetch_all_genes_paginated_graphql(client: AGRCurationAPIClient, fields: str, page_size: int = 1000) -> List[Gene]:
    """Fetch all genes using pagination with GraphQL.

    Args:
        client: API client instance
        fields: Field specification (minimal, basic, standard, full)
        page_size: Number of records per page

    Returns:
        List of all genes
    """
    all_genes = []
    page = 0

    while True:
        genes = client.get_genes(taxon="NCBITaxon:6239", limit=page_size, page=page, fields=fields)
        if not genes:
            break
        all_genes.extend(genes)
        page += 1

    return all_genes


def benchmark_all_data_sources(limit: int = 100, runs: int = 3):
    """Benchmark REST API vs GraphQL vs Database with different field sets.

    Args:
        limit: Number of records to fetch per test
        runs: Number of times to run each test for averaging

    Returns:
        bool: True if successful, False otherwise
    """
    print("="*70)
    print("PERFORMANCE BENCHMARK: REST API vs GraphQL vs Database")
    print("="*70)
    print(f"Configuration: {limit} records, {runs} runs per test")
    print(f"Testing with WB (WormBase) genes")
    print(f"Note: REST API uses data_provider='WB', GraphQL/DB use taxon='NCBITaxon:6239'")

    results = {}
    gene_counts = {}  # Track gene counts per method for validation
    db_available = True

    # Create clients for each data source
    api_client = AGRCurationAPIClient(data_source="api")
    graphql_client = AGRCurationAPIClient(data_source="graphql")

    # Try to create database client and test it
    try:
        db_client = AGRCurationAPIClient(data_source="db")
        # Test if database is actually accessible by trying a minimal query
        print("\nTesting database connectivity...")
        test_genes = db_client.get_genes(taxon="NCBITaxon:6239", limit=1, include_obsolete=False)
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
        genes_sample = None
        for run in range(runs):
            start = time.time()
            genes = api_client.get_genes(data_provider="WB", limit=limit, include_obsolete=False)
            elapsed = time.time() - start
            rest_times.append(elapsed)
            if run == 0:
                genes_sample = genes  # Save first run for count validation
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        rest_avg = sum(rest_times) / len(rest_times)
        results['REST API (all fields)'] = rest_avg
        gene_counts['REST API (all fields)'] = len(genes_sample)
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
                genes = db_client.get_genes(taxon="NCBITaxon:6239", limit=limit, include_obsolete=False)
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


def benchmark_pagination_strategies(page_size: int = 1000):
    """Benchmark different pagination strategies for fetching all genes.

    Compares:
    1. Single large request (limit=100000)
    2. Paginated requests (page_size=1000)

    Args:
        page_size: Number of records per page for pagination test

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "="*70)
    print("PAGINATION STRATEGY BENCHMARK: Single Request vs Paginated")
    print("="*70)
    print(f"Goal: Fetch ALL WB genes")
    print(f"Paginated approach uses page_size={page_size}")

    results = {}
    gene_counts = {}  # Track gene counts per method

    # Create clients for each data source
    api_client = AGRCurationAPIClient(data_source="api")
    graphql_client = AGRCurationAPIClient(data_source="graphql")

    # Test database availability
    db_available = True
    try:
        db_client = AGRCurationAPIClient(data_source="db")
        print("\nTesting database connectivity...")
        test_genes = db_client.get_genes(taxon="NCBITaxon:6239", limit=1, include_obsolete=False)
        if not test_genes:
            print("⚠️  Database returned no results")
            db_available = False
            db_client = None
        else:
            print("✓ Database connection successful")
    except Exception as e:
        print(f"⚠️  Database not available: {e}")
        db_available = False
        db_client = None

    try:
        # Test 1: REST API - Single large request
        print("\n--- Test 1: REST API (single request, limit=100000) ---")
        start = time.time()
        genes_rest_single = api_client.get_genes(data_provider="WB", limit=100000, include_obsolete=False)
        elapsed = time.time() - start
        results['REST API (single)'] = elapsed
        gene_counts['REST API (single)'] = len(genes_rest_single)
        print(f"  Time: {elapsed:.3f}s ({len(genes_rest_single)} genes)")

        # Test 2: REST API - Paginated
        print(f"\n--- Test 2: REST API (paginated, page_size={page_size}) ---")
        start = time.time()
        genes_rest_paged = fetch_all_genes_paginated(api_client, page_size=page_size)
        elapsed = time.time() - start
        results['REST API (paginated)'] = elapsed
        gene_counts['REST API (paginated)'] = len(genes_rest_paged)
        pages_used = len(genes_rest_paged) // page_size + (1 if len(genes_rest_paged) % page_size else 0)
        print(f"  Time: {elapsed:.3f}s ({len(genes_rest_paged)} genes, {pages_used} pages)")

        # Test 3: GraphQL minimal - Single large request
        print("\n--- Test 3: GraphQL minimal (single request, limit=100000) ---")
        start = time.time()
        genes_gql_single = graphql_client.get_genes(taxon="NCBITaxon:6239", limit=100000, fields="minimal")
        elapsed = time.time() - start
        results['GraphQL minimal (single)'] = elapsed
        gene_counts['GraphQL minimal (single)'] = len(genes_gql_single)
        print(f"  Time: {elapsed:.3f}s ({len(genes_gql_single)} genes)")

        # Test 4: GraphQL minimal - Paginated
        print(f"\n--- Test 4: GraphQL minimal (paginated, page_size={page_size}) ---")
        start = time.time()
        genes_gql_paged = fetch_all_genes_paginated_graphql(graphql_client, fields="minimal", page_size=page_size)
        elapsed = time.time() - start
        results['GraphQL minimal (paginated)'] = elapsed
        gene_counts['GraphQL minimal (paginated)'] = len(genes_gql_paged)
        pages_used = len(genes_gql_paged) // page_size + (1 if len(genes_gql_paged) % page_size else 0)
        print(f"  Time: {elapsed:.3f}s ({len(genes_gql_paged)} genes, {pages_used} pages)")

        # Test 5: Database - Single request (no pagination needed with SQL)
        if db_available and db_client:
            print("\n--- Test 5: Database (single SQL query, no pagination) ---")
            start = time.time()
            genes_db = db_client.get_genes(taxon="NCBITaxon:6239", limit=100000, include_obsolete=False)
            elapsed = time.time() - start
            results['Database (single)'] = elapsed
            gene_counts['Database (single)'] = len(genes_db)
            print(f"  Time: {elapsed:.3f}s ({len(genes_db)} genes)")

        # Validate gene counts are consistent
        print("\n" + "="*70)
        print("GENE COUNT VALIDATION")
        print("="*70)

        unique_counts = set(gene_counts.values())
        all_counts = list(gene_counts.values())

        if len(unique_counts) == 1:
            print(f"✅ All methods returned the same count: {all_counts[0]} genes")
            print("   Data consistency verified across all approaches!")
        else:
            print("⚠️  WARNING: Gene counts are INCONSISTENT across methods!")
            print("   This may indicate:")
            print("   - API/GraphQL has internal limits")
            print("   - Different filtering behavior (data_provider vs taxon)")
            print("   - Database contains different data than API")
            print("\n   Detailed counts:")
            for method, count in gene_counts.items():
                print(f"   {method:<40} {count:>6} genes")

            # Find min and max
            min_count = min(all_counts)
            max_count = max(all_counts)
            diff = max_count - min_count
            print(f"\n   Range: {min_count} to {max_count} (difference: {diff} genes)")

        # Summary table
        print("\n" + "="*70)
        print("PAGINATION STRATEGY SUMMARY")
        print("="*70)
        print(f"{'Method':<40} {'Time (s)':<12} {'Genes':<10} {'Notes':<15}")
        print("-"*70)

        for method, time_taken in results.items():
            count = gene_counts[method]
            if 'single' in method.lower():
                note = "1 request"
            elif 'paginated' in method.lower():
                pages = count // page_size + (1 if count % page_size else 0)
                note = f"{pages} requests"
            else:
                note = "Direct SQL"
            print(f"{method:<40} {time_taken:>8.3f}s    {count:>6}     {note:<15}")

        print("\n" + "="*70)

        # Analysis
        print("\n💡 Key Findings:")

        # Compare REST API strategies
        if 'REST API (single)' in results and 'REST API (paginated)' in results:
            single = results['REST API (single)']
            paginated = results['REST API (paginated)']
            if single < paginated:
                speedup = paginated / single
                print(f"   - REST API: Single request is {speedup:.2f}x FASTER than paginated")
            else:
                speedup = single / paginated
                print(f"   - REST API: Paginated is {speedup:.2f}x FASTER than single request")

        # Compare GraphQL strategies
        if 'GraphQL minimal (single)' in results and 'GraphQL minimal (paginated)' in results:
            single = results['GraphQL minimal (single)']
            paginated = results['GraphQL minimal (paginated)']
            if single < paginated:
                speedup = paginated / single
                print(f"   - GraphQL: Single request is {speedup:.2f}x FASTER than paginated")
            else:
                speedup = single / paginated
                print(f"   - GraphQL: Paginated is {speedup:.2f}x FASTER than single request")

        # Compare overall
        fastest = min(results.items(), key=lambda x: x[1])
        print(f"\n   🏆 Fastest overall: {fastest[0]} ({fastest[1]:.3f}s)")

        print("\n   Recommendations:")
        print("   - For bulk downloads: Use single large request if server allows")
        print("   - For memory efficiency: Use pagination with smaller page sizes")
        print("   - For maximum speed: Database access beats all API approaches")

        print("\n✓ Pagination benchmark completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Error during benchmark: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the performance benchmark."""
    print("="*70)
    print("AGR CURATION API PERFORMANCE BENCHMARK SUITE")
    print("="*70)
    print("\nThis benchmark suite includes:")
    print("1. Field selection comparison (minimal, basic, standard, full)")
    print("2. Pagination strategy comparison (single vs paginated requests)")
    print("="*70)

    # Quick test with 100 records
    print("\n" + "="*70)
    print("QUICK TEST: 100 records, 3 runs")
    print("="*70)
    success = benchmark_all_data_sources(limit=100, runs=3)

    # Medium test with 1000 records
    if success:
        print("\n" + "="*70)
        print("MEDIUM TEST: 1000 records, 3 runs")
        print("="*70)
        success = benchmark_all_data_sources(limit=1000, runs=3)

    # Pagination strategy comparison - fetch ALL genes
    if success:
        success = benchmark_pagination_strategies(page_size=1000)

    # Final summary
    print("\n" + "="*70)
    print("BENCHMARK SUITE COMPLETED")
    print("="*70)
    if success:
        print("✅ All benchmarks completed successfully!")
    else:
        print("⚠️  Some benchmarks failed or were skipped")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())