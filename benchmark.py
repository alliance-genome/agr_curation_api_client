#!/usr/bin/env python
"""Benchmark script to compare REST API vs GraphQL performance."""

import sys
import time
sys.path.insert(0, 'src')

from agr_curation_api import AGRCurationAPIClient, APIConfig


def benchmark_rest_vs_graphql(client: AGRCurationAPIClient, limit: int = 100, runs: int = 3):
    """Benchmark REST API vs GraphQL with different field sets.

    Args:
        client: AGR API client instance
        limit: Number of records to fetch per test
        runs: Number of times to run each test for averaging

    Returns:
        bool: True if successful, False otherwise
    """
    print("="*70)
    print("PERFORMANCE BENCHMARK: REST API vs GraphQL")
    print("="*70)
    print(f"Configuration: {limit} records, {runs} runs per test")
    print(f"Testing with WB (WormBase) genes")

    results = {}

    try:
        # Test 1: REST API (all fields)
        print("\n--- Test 1: REST API (all fields) ---")
        rest_times = []
        for run in range(runs):
            start = time.time()
            genes = client.get_genes(data_provider="WB", limit=limit)
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
            genes = client.get_genes_graphql(
                fields="minimal",
                data_provider="WB",
                limit=limit
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
            genes = client.get_genes_graphql(
                fields="basic",
                data_provider="WB",
                limit=limit
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
            genes = client.get_genes_graphql(
                fields="standard",
                data_provider="WB",
                limit=limit
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
            genes = client.get_genes_graphql(
                fields="full",
                data_provider="WB",
                limit=limit
            )
            elapsed = time.time() - start
            full_times.append(elapsed)
            print(f"  Run {run+1}: {elapsed:.3f}s ({len(genes)} genes)")

        full_avg = sum(full_times) / len(full_times)
        results['GraphQL (full)'] = full_avg
        print(f"  Average: {full_avg:.3f}s")

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

        print("\n✓ Performance benchmark completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Error during benchmark: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run the performance benchmark."""
    # Setup client
    try:
        config = APIConfig()
        client = AGRCurationAPIClient(config)
        print("✓ Client initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return 1

    # Run benchmark with different configurations
    print("Running benchmarks with different configurations...\n")

    # Quick test with 50 records
    print("\n" + "="*70)
    print("QUICK TEST: 50 records, 3 runs")
    print("="*70)
    success = benchmark_rest_vs_graphql(client, limit=50, runs=3)

    # Larger test with 200 records
    if success:
        print("\n" + "="*70)
        print("LARGER TEST: 200 records, 3 runs")
        print("="*70)
        success = benchmark_rest_vs_graphql(client, limit=200, runs=3)

    # Even larger test with 500 records
    if success:
        print("\n" + "="*70)
        print("LARGE SCALE TEST: 500 records, 3 runs")
        print("="*70)
        success = benchmark_rest_vs_graphql(client, limit=500, runs=3)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())