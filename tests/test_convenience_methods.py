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


    # Test C. elegans anatomy
    results = db.search_anatomy_terms('linker', 'WB', limit=3)
    for r in results:

    # Test Drosophila anatomy
    results = db.search_anatomy_terms('wing', 'FB', limit=3)
    for r in results:

    # Test Zebrafish anatomy
    results = db.search_anatomy_terms('somite', 'ZFIN', limit=3)
    for r in results:


def test_life_stage_methods():
    """Test life stage search convenience methods."""
    db = DatabaseMethods()


    # Test C. elegans life stages
    results = db.search_life_stage_terms('L3', 'WB', limit=3)
    for r in results:

    # Test Drosophila life stages
    results = db.search_life_stage_terms('larval', 'FB', limit=3)
    for r in results:

    # Test Zebrafish life stages
    results = db.search_life_stage_terms('adult', 'ZFIN', limit=3)
    for r in results:


def test_go_methods():
    """Test GO term search convenience methods."""
    db = DatabaseMethods()


    # Test cellular component search
    results = db.search_go_terms('nucleus', go_aspect='cellular_component', limit=3)
    for r in results:

    # Test biological process search
    results = db.search_go_terms('apoptosis', go_aspect='biological_process', limit=3)
    for r in results:

    # Test molecular function search
    results = db.search_go_terms('kinase', go_aspect='molecular_function', limit=3)
    for r in results:

    # Test all GO aspects (no filtering)
    results = db.search_go_terms('cell', go_aspect=None, limit=5)
    for r in results:


def test_organism_switching():
    """Test organism switching with same search term."""
    db = DatabaseMethods()


    search_term = 'brain'


    # C. elegans
    wb_results = db.search_anatomy_terms(search_term, 'WB', limit=2)
    for r in wb_results:

    # Drosophila
    fb_results = db.search_anatomy_terms(search_term, 'FB', limit=2)
    for r in fb_results:

    # Zebrafish
    zfin_results = db.search_anatomy_terms(search_term, 'ZFIN', limit=2)
    for r in zfin_results:

    # Mouse
    mgi_results = db.search_anatomy_terms(search_term, 'MGI', limit=2)
    for r in mgi_results:



if __name__ == '__main__':

    try:
        test_anatomy_methods()
        test_life_stage_methods()
        test_go_methods()
        test_organism_switching()


    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
