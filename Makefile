.PHONY: help test test-unit test-integration test-cov lint type-check format check-format check-security check-updates install install-dev clean check all

# Default target when `make` is run without arguments
help:
	@echo "Available commands:"
	@echo "  make help             - Show this help message"
	@echo "  make install          - Install the package in development mode"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make test             - Run all tests"
	@echo "  make test-unit        - Run unit tests"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-cov         - Run tests with coverage report"
	@echo "  make lint             - Run code linters (ruff, mypy)"
	@echo "  make type-check       - Run type checking with mypy"
	@echo "  make format           - Format code with Ruff, Black, and isort"
	@echo "  make check-format     - Check code formatting without making changes"
	@echo "  make check-security   - Run security checks (safety, bandit)"
	@echo "  make check-updates    - Check for outdated dependencies"
	@echo "  make clean            - Remove build artifacts and caches"
	@echo "  make check            - Run format check, lint, and tests"
	@echo "  make all              - Auto-format and run all checks"

# Install the package in development mode
install:
	pip install -e .

# Install development dependencies
install-dev:
	pip install -e ".[test,all]"

# Run all tests
test:
	pytest tests/

# Run unit tests only
test-unit:
	pytest tests/unit/

# Run integration tests only
test-integration:
	pytest tests/integration/

# Run tests with coverage report
test-cov:
	pytest --cov=src --cov-report=term-missing --cov-report=xml

# Lint the code
lint:
	@echo "Running Ruff..."
	@ruff check src/ tests/
	@echo "Running mypy..."
	@mypy src/ tests/

# Run type checking
type-check:
	mypy src/ tests/

# Format the code
format:
	@echo "Running Ruff with --fix..."
	@ruff check src/ tests/ --fix
	@echo "Running isort..."
	@isort src/ tests/
	@echo "Running Black..."
	@black src/ tests/

# Check code formatting without making changes
check-format:
	@echo "Checking Ruff formatting..."
	@ruff format --check src/ tests/
	@echo "Checking Black formatting..."
	@black --check src/ tests/
	@echo "Checking isort formatting..."
	@isort --check-only src/ tests/

# Run security checks
check-security:
	@echo "Checking for vulnerable dependencies with safety..."
	@pip freeze | safety check --stdin
	@echo "Running bandit security linter..."
	@bandit -r src -c pyproject.toml

# Check for outdated dependencies
check-updates:
	@echo "Outdated packages:"
	@pip list --outdated

# Clean up build artifacts and caches
clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.py[co]" -delete
	@rm -rf \
		.pytest_cache/ \
		.mypy_cache/ \
		.coverage \
		htmlcov/ \
		*.xml \
		*.egg-info/ \
		dist/ \
		build/

# Run all checks (format check, lint, test)
check: check-format lint test

# Run all checks with auto-formatting
# 1. First formats the code
# 2. Verifies formatting is correct
# 3. Runs lint and tests
all: format check-format lint test