# Cisco IOS XE gNMI Collection - Makefile

.PHONY: help install test lint clean docs

help:
	@echo "Cisco IOS XE gNMI Ansible Collection - Make targets"
	@echo ""
	@echo "Available targets:"
	@echo "  install      - Install dependencies and collection"
	@echo "  test         - Run unit tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo "  lint         - Run code quality checks"
	@echo "  format       - Format code with black"
	@echo "  clean        - Remove build artifacts"
	@echo "  docs         - Generate documentation"
	@echo "  build        - Build collection tarball"
	@echo "  examples     - Run example playbooks (check mode)"
	@echo ""

install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Installing test dependencies..."
	pip install -r tests/requirements.txt
	@echo "Installing Ansible collection..."
	ansible-galaxy collection install . --force
	@echo "✓ Installation complete"

test:
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-cov:
	@echo "Running tests with coverage..."
	pytest tests/unit/ -v --cov=plugins --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/"

lint:
	@echo "Running pylint..."
	pylint plugins/ || true
	@echo "Running flake8..."
	flake8 plugins/ || true
	@echo "Running ansible-lint..."
	ansible-lint examples/*.yml || true

format:
	@echo "Formatting code with black..."
	black plugins/ tests/

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✓ Clean complete"

docs:
	@echo "Generating documentation..."
	ansible-doc cisco.iosxe_gnmi.cisco_iosxe_gnmi > docs/module_documentation.txt
	@echo "✓ Documentation generated in docs/"

build:
	@echo "Building collection..."
	ansible-galaxy collection build --force
	@echo "✓ Build complete"

examples:
	@echo "Running GET examples (check mode)..."
	ansible-playbook -i examples/inventory.ini examples/get_operations.yml --check || true
	@echo ""
	@echo "Running SET examples (check mode)..."
	ansible-playbook -i examples/inventory.ini examples/set_operations.yml --check || true
	@echo ""
	@echo "Running Subscribe examples (check mode)..."
	ansible-playbook -i examples/inventory.ini examples/subscribe_operations.yml --check || true

dev-setup:
	@echo "Setting up development environment..."
	pip install -r requirements.txt
	pip install -r tests/requirements.txt
	pip install black pylint flake8 ansible-lint
	@echo "✓ Development environment ready"

.DEFAULT_GOAL := help
