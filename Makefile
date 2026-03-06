# cisco.gnmi Ansible Collection - Makefile

.PHONY: help install test test-cov lint clean build sanity

help:
	@echo "cisco.gnmi Ansible Collection"
	@echo ""
	@echo "  install   - Install dependencies and collection"
	@echo "  test      - Run unit tests"
	@echo "  test-cov  - Run tests with coverage"
	@echo "  lint      - Run code quality checks"
	@echo "  sanity    - Run ansible-test sanity"
	@echo "  build     - Build collection tarball"
	@echo "  clean     - Remove build artifacts"

install:
	pip install -r requirements.txt
	pip install -r tests/requirements.txt
	ansible-galaxy collection install . --force

test:
	pytest tests/unit/ -v

test-cov:
	pytest tests/unit/ -v --cov=plugins --cov-report=term-missing

lint:
	flake8 plugins/ --max-line-length=120 || true
	ansible-lint examples/*.yml || true

sanity:
	ansible-test sanity --docker default -v

build:
	ansible-galaxy collection build --force

clean:
	rm -rf .pytest_cache htmlcov .coverage *.tar.gz
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

.DEFAULT_GOAL := help
