.PHONY: help install install-dev test lint type-check format clean build upload sync-models test-models run-example clean-models check-models

help:
	@echo "Available commands:"
	@echo "  make install       Install package"
	@echo "  make install-dev   Install package with dev dependencies"
	@echo "  make test          Run tests"
	@echo "  make lint          Run linting"
	@echo "  make type-check    Run type checking"
	@echo "  make format        Format code with black"
	@echo "  make clean         Clean build artifacts"
	@echo "  make build         Build distribution packages"
	@echo "  make upload        Upload to PyPI"
	@echo ""
	@echo "LinkML Model Management:"
	@echo "  make sync-models   Fetch schemas and generate Pydantic models"
	@echo "  make test-models   Test generated models"
	@echo "  make run-example   Run main.py example"
	@echo "  make clean-models  Clean generated model files"
	@echo "  make check-models  Check if models are up to date"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	flake8 src/agr_curation_api tests

type-check:
	mypy src/agr_curation_api

format:
	black src/agr_curation_api tests

clean:
	rm -rf build dist *.egg-info
	rm -rf .coverage htmlcov .pytest_cache .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build: clean
	python -m build

upload: build
	python -m twine upload dist/*

# Development shortcuts
check: lint type-check
	@echo "All checks passed!"

dev: install-dev
	@echo "Development environment ready!"

test-all: lint type-check test
	@echo "All tests and checks passed!"

# LinkML Model Management Commands
sync-models:
	@echo "🔄 Syncing schemas and generating Pydantic models..."
	python scripts/sync_and_generate.py
	@echo "✅ Models generated successfully!"

test-models:
	@echo "🧪 Testing generated models..."
	python -m pytest tests/ -v -k "test_models or test_nested"

run-example:
	@echo "🚀 Running example script..."
	python main.py

clean-models:
	@echo "🧹 Cleaning generated models..."
	rm -rf src/agr_curation_api/generated_models/
	rm -rf .schema_cache/

check-models:
	@echo "🔍 Checking if models are up to date..."
	@if [ -f .schema_cache/last_sync.json ]; then \
		echo "Last sync: $$(cat .schema_cache/last_sync.json | python -c 'import json,sys; print(json.load(sys.stdin)["generated_at"])' 2>/dev/null || echo 'Unknown')"; \
	else \
		echo "Models have never been generated. Run 'make sync-models'"; \
	fi