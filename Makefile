.PHONY: test test-unit test-integration test-cov lint format install install-dev clean

# Install development dependencies
install-dev:
	pip install -e .
	pip install -r requirements-test.txt

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
	flake8 src/
	mypy src/

# Format the code
format:
	black src/
	isort src/

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -r {} \;
	rm -rf .pytest_cache/ .mypy_cache/ .coverage htmlcov/ *.xml
