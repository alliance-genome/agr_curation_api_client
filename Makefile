.PHONY: help install install-dev test lint type-check format clean build upload run-example

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
	@echo "  make run-example   Run main.py example"

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

run-example:
	@echo "🚀 Running example script..."
	python main.py