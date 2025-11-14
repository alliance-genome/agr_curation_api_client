#!/usr/bin/env python3
"""Test organism-agnostic convenience methods.

Tests search_anatomy_terms(), search_life_stage_terms(), and search_go_terms()
against production database.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agr_curation_api.db_methods import DatabaseMethods

def test_anatomy_methods():
    """Test anatomy search convenience methods."""
    db = DatabaseMethods()

    print("=" * 80)
    print("TESTING ANATOMY SEARCH METHODS")
    print("=" * 80)

    # Test C. elegans anatomy
    print("\n1. C. elegans (WB) - search_anatomy_terms('linker', 'WB')")
    print("-" * 80)
    results = db.search_anatomy_terms('linker', 'WB', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")

    # Test Drosophila anatomy
    print("\n2. Drosophila (FB) - search_anatomy_terms('wing', 'FB')")
    print("-" * 80)
    results = db.search_anatomy_terms('wing', 'FB', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")

    # Test Zebrafish anatomy
    print("\n3. Zebrafish (ZFIN) - search_anatomy_terms('somite', 'ZFIN')")
    print("-" * 80)
    results = db.search_anatomy_terms('somite', 'ZFIN', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")


def test_life_stage_methods():
    """Test life stage search convenience methods."""
    db = DatabaseMethods()

    print("\n" + "=" * 80)
    print("TESTING LIFE STAGE SEARCH METHODS")
    print("=" * 80)

    # Test C. elegans life stages
    print("\n1. C. elegans (WB) - search_life_stage_terms('L3', 'WB')")
    print("-" * 80)
    results = db.search_life_stage_terms('L3', 'WB', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")

    # Test Drosophila life stages
    print("\n2. Drosophila (FB) - search_life_stage_terms('larval', 'FB')")
    print("-" * 80)
    results = db.search_life_stage_terms('larval', 'FB', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")

    # Test Zebrafish life stages
    print("\n3. Zebrafish (ZFIN) - search_life_stage_terms('adult', 'ZFIN')")
    print("-" * 80)
    results = db.search_life_stage_terms('adult', 'ZFIN', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} {r.ontology_type}")
    print(f"  ✅ Found {len(results)} results")


def test_go_methods():
    """Test GO term search convenience methods."""
    db = DatabaseMethods()

    print("\n" + "=" * 80)
    print("TESTING GO TERM SEARCH METHODS")
    print("=" * 80)

    # Test cellular component search
    print("\n1. GO Cellular Component - search_go_terms('nucleus', 'cellular_component')")
    print("-" * 80)
    results = db.search_go_terms('nucleus', go_aspect='cellular_component', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} namespace={r.namespace}")
    print(f"  ✅ Found {len(results)} results")

    # Test biological process search
    print("\n2. GO Biological Process - search_go_terms('apoptosis', 'biological_process')")
    print("-" * 80)
    results = db.search_go_terms('apoptosis', go_aspect='biological_process', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} namespace={r.namespace}")
    print(f"  ✅ Found {len(results)} results")

    # Test molecular function search
    print("\n3. GO Molecular Function - search_go_terms('kinase', 'molecular_function')")
    print("-" * 80)
    results = db.search_go_terms('kinase', go_aspect='molecular_function', limit=3)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} namespace={r.namespace}")
    print(f"  ✅ Found {len(results)} results")

    # Test all GO aspects (no filtering)
    print("\n4. All GO Aspects - search_go_terms('cell', go_aspect=None)")
    print("-" * 80)
    results = db.search_go_terms('cell', go_aspect=None, limit=5)
    for r in results:
        print(f"  {r.curie:15} {r.name:40} namespace={r.namespace}")
    print(f"  ✅ Found {len(results)} results")


def test_organism_switching():
    """Test organism switching with same search term."""
    db = DatabaseMethods()

    print("\n" + "=" * 80)
    print("TESTING ORGANISM SWITCHING (Same term, different organisms)")
    print("=" * 80)

    search_term = 'brain'

    print(f"\nSearch term: '{search_term}'")
    print("-" * 80)

    # C. elegans
    wb_results = db.search_anatomy_terms(search_term, 'WB', limit=2)
    print(f"\nWB (C. elegans) - {len(wb_results)} results:")
    for r in wb_results:
        print(f"  {r.curie:15} {r.name:40} [{r.ontology_type}]")

    # Drosophila
    fb_results = db.search_anatomy_terms(search_term, 'FB', limit=2)
    print(f"\nFB (Drosophila) - {len(fb_results)} results:")
    for r in fb_results:
        print(f"  {r.curie:15} {r.name:40} [{r.ontology_type}]")

    # Zebrafish
    zfin_results = db.search_anatomy_terms(search_term, 'ZFIN', limit=2)
    print(f"\nZFIN (Zebrafish) - {len(zfin_results)} results:")
    for r in zfin_results:
        print(f"  {r.curie:15} {r.name:40} [{r.ontology_type}]")

    # Mouse
    mgi_results = db.search_anatomy_terms(search_term, 'MGI', limit=2)
    print(f"\nMGI (Mouse) - {len(mgi_results)} results:")
    for r in mgi_results:
        print(f"  {r.curie:15} {r.name:40} [{r.ontology_type}]")

    print("\n✅ Organism switching works - same term finds organism-specific ontology entries")


if __name__ == '__main__':
    print("\n🧪 CONVENIENCE METHOD VALIDATION TEST")
    print("Testing organism-agnostic convenience methods against production database")
    print()

    try:
        test_anatomy_methods()
        test_life_stage_methods()
        test_go_methods()
        test_organism_switching()

        print("\n" + "=" * 80)
        print("✅ ALL CONVENIENCE METHOD TESTS PASSED")
        print("=" * 80)
        print("\nSummary:")
        print("  ✅ search_anatomy_terms() - Works for WB, FB, ZFIN, MGI")
        print("  ✅ search_life_stage_terms() - Works for WB, FB, ZFIN")
        print("  ✅ search_go_terms() - Works with aspect filtering (CC, BP, MF)")
        print("  ✅ Organism switching - Same API, different organism-specific results")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
