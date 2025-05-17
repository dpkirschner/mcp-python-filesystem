.PHONY: help test test-unit test-integration test-cov lint type-check format check-format check-security check-updates install install-dev clean

# Default target when `make` is run without arguments
help:
	@echo "Available commands:"
	@echo "  make help             - Show this help message"
	@echo "  make install          - Install the package in development mode"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make test             - Run all tests"
	@echo "  test-unit            - Run unit tests"
	@echo "  test-integration     - Run integration tests"
	@echo "  test-cov             - Run tests with coverage report"
	@echo "  lint                 - Run code linters (flake8, mypy)"
	@echo "  type-check           - Run type checking with mypy"
	@echo "  format               - Format code with Black and isort"
	@echo "  check-format         - Check code formatting without making changes"
	@echo "  check-security       - Run security checks (safety, bandit)"
	@echo "  check-updates        - Check for outdated dependencies"
	@echo "  clean                - Remove build artifacts and caches"

# Install the package in development mode
install:
	pip install -e .

# Install development dependencies
install-dev:
	pip install -e ".[test]"

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
	@echo "Running flake8..."
	@flake8 src/ tests/
	@echo "Running mypy..."
	@mypy src/ tests/

# Run type checking
type-check:
	mypy src/ tests/

# Format the code
format:
	@echo "Running isort..."
	@isort src/ tests/
	@echo "Running black..."
	@black src/ tests/

# Check code formatting without making changes
check-format:
	@echo "Checking code formatting..."
	@black --check --diff src/ tests/
	@isort --check-only --diff src/ tests/

# Run security checks
check-security:
	@echo "Checking for vulnerable dependencies..."
	@pip freeze | safety check --stdin
	@echo "\nRunning bandit security linter..."
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

# Run all checks (format, lint, test)
check: check-format lint test

# Run all checks and format code
all: format lint test
