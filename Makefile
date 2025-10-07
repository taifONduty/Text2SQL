.PHONY: install setup test coverage clean docker-up docker-down help

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt

download-data:  ## Download Northwind database
	python scripts/download_northwind.py

setup: install download-data  ## Full setup (install + download data + setup database)
	python scripts/setup_database.py

test:  ## Run all tests
	pytest tests/ -v

coverage:  ## Run tests with coverage report
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "\nCoverage report generated at: htmlcov/index.html"

evaluate:  ## Run accuracy evaluation
	python scripts/run_evaluation.py

docker-up:  ## Start Docker containers
	docker-compose up -d
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 10
	@echo "PostgreSQL is ready!"

docker-down:  ## Stop Docker containers
	docker-compose down

docker-setup: docker-up download-data  ## Setup with Docker
	python scripts/setup_database.py

format:  ## Format code with black
	black src/ tests/ scripts/

lint:  ## Lint code with flake8
	flake8 src/ tests/ scripts/

type-check:  ## Type check with mypy
	mypy src/

qa: format lint type-check  ## Run all code quality checks

clean:  ## Clean temporary files
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '*.log' -delete
	rm -rf .pytest_cache .coverage htmlcov/ dist/ build/ *.egg-info

clean-db:  ## Clean database (WARNING: deletes all data)
	@echo "WARNING: This will delete the database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		psql -U postgres -c "DROP DATABASE IF EXISTS northwind;"; \
		psql -U postgres -c "DROP DATABASE IF EXISTS northwind_test;"; \
		echo "Databases dropped."; \
	fi

all: install setup test coverage  ## Run complete setup and testing

.DEFAULT_GOAL := help

