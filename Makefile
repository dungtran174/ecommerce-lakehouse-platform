# ==============================================================================
# Modern E-Commerce Data Lakehouse Platform
# Automation & Developer Experience Makefile
# ==============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

# Configuration Variables
PYTHON := python3
PIP := pip
DOCKER_COMPOSE_FILE := docker/docker-compose.yml
DBT_PROJECT_DIR := dbt

# Color formatting
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_CYAN := \033[36m

.PHONY: help setup install install-dev lint format test clean \
        docker-up docker-down docker-restart docker-logs docker-ps \
        init-lakehouse seed-data dbt-deps dbt-compile dbt-run dbt-test \
        k8s-deploy k8s-delete

help: ## Display this interactive help menu with all available commands
	@echo -e "$(COLOR_BOLD)$(COLOR_CYAN)E-Commerce Data Lakehouse Platform - Management Commands:$(COLOR_RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-20s$(COLOR_RESET) %s\n", $$1, $$2}'

# ==============================================================================
# Environment & Dependency Management
# ==============================================================================

setup: install-dev ## Create virtual environment and install all dependencies
	@echo -e "$(COLOR_GREEN)Setting up git pre-commit hooks...$(COLOR_RESET)"
	pre-commit install

install: ## Install production runtime dependencies
	@echo -e "$(COLOR_GREEN)Installing production dependencies...$(COLOR_RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: ## Install development, linting, and testing dependencies
	@echo -e "$(COLOR_GREEN)Installing development dependencies...$(COLOR_RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

# ==============================================================================
# Code Quality, Formatting & Testing
# ==============================================================================

lint: ## Run all linters (Black, isort, Flake8, SQLFluff)
	@echo -e "$(COLOR_YELLOW)Checking code formatting with Black...$(COLOR_RESET)"
	black --check --diff .
	@echo -e "$(COLOR_YELLOW)Checking import sorting with isort...$(COLOR_RESET)"
	isort --check-only --diff .
	@echo -e "$(COLOR_YELLOW)Linting Python code with Flake8...$(COLOR_RESET)"
	flake8 .
	@echo -e "$(COLOR_YELLOW)Linting SQL models with SQLFluff...$(COLOR_RESET)"
	@if [ -d "$(DBT_PROJECT_DIR)/models" ] && [ "$$(find $(DBT_PROJECT_DIR)/models -name '*.sql' | wc -l)" -gt 0 ]; then \
		sqlfluff lint $(DBT_PROJECT_DIR)/models --dialect sparksql; \
	else \
		echo "No SQL models to lint yet."; \
	fi

format: ## Automatically format Python and SQL source code
	@echo -e "$(COLOR_GREEN)Formatting Python code with Black and isort...$(COLOR_RESET)"
	black .
	isort .
	@echo -e "$(COLOR_GREEN)Formatting SQL models with SQLFluff...$(COLOR_RESET)"
	@if [ -d "$(DBT_PROJECT_DIR)/models" ] && [ "$$(find $(DBT_PROJECT_DIR)/models -name '*.sql' | wc -l)" -gt 0 ]; then \
		sqlfluff fix --force $(DBT_PROJECT_DIR)/models --dialect sparksql; \
	fi

test: ## Run unit and integration tests with coverage report
	@echo -e "$(COLOR_GREEN)Running test suite with pytest...$(COLOR_RESET)"
	pytest -v --cov=. --cov-report=term-missing tests/

clean: ## Remove compiled Python files, caches, and dbt build artifacts
	@echo -e "$(COLOR_YELLOW)Cleaning caches and temporary artifacts...$(COLOR_RESET)"
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -rf dbt/target dbt/dbt_packages dbt/logs

# ==============================================================================
# Local Infrastructure & Docker Services
# ==============================================================================

docker-up: ## Start all Lakehouse Docker services (MinIO, Spark, Trino, Airflow, Metabase)
	@echo -e "$(COLOR_GREEN)Starting container services in background...$(COLOR_RESET)"
	docker compose -f $(DOCKER_COMPOSE_FILE) up -d

docker-down: ## Stop and remove all running containers and networks
	@echo -e "$(COLOR_YELLOW)Stopping and tearing down containers...$(COLOR_RESET)"
	docker compose -f $(DOCKER_COMPOSE_FILE) down

docker-restart: docker-down docker-up ## Restart all Docker services

docker-logs: ## Follow logs of all active containers
	docker compose -f $(DOCKER_COMPOSE_FILE) logs -f

docker-ps: ## List running container status and port mappings
	docker compose -f $(DOCKER_COMPOSE_FILE) ps

# ==============================================================================
# Data Pipeline & Lakehouse Operations
# ==============================================================================

init-lakehouse: ## Initialize MinIO buckets and Hive Metastore schemas
	@echo -e "$(COLOR_GREEN)Initializing MinIO buckets and Lakehouse storage...$(COLOR_RESET)"
	bash scripts/init_minio.sh

seed-data: ## Generate synthetic e-commerce datasets (MySQL & Clickstream Logs)
	@echo -e "$(COLOR_GREEN)Generating synthetic E-Commerce datasets...$(COLOR_RESET)"
	$(PYTHON) data_generators/generate_oltp_data.py --scale small
	$(PYTHON) data_generators/generate_clickstream_logs.py --days 7

dbt-deps: ## Install dbt external packages
	@echo -e "$(COLOR_GREEN)Installing dbt packages...$(COLOR_RESET)"
	dbt deps --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROJECT_DIR)

dbt-compile: ## Compile all dbt SQL models without execution
	@echo -e "$(COLOR_GREEN)Compiling dbt models...$(COLOR_RESET)"
	dbt compile --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROJECT_DIR)

dbt-run: ## Execute dbt models on Spark Thrift Server (Bronze -> Silver -> Gold)
	@echo -e "$(COLOR_GREEN)Running dbt transformation models...$(COLOR_RESET)"
	dbt run --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROJECT_DIR)

dbt-test: ## Run schema and data quality assertions
	@echo -e "$(COLOR_GREEN)Running dbt data quality tests...$(COLOR_RESET)"
	dbt test --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROJECT_DIR)

# ==============================================================================
# Kubernetes Deployment Operations
# ==============================================================================

k8s-deploy: ## Apply all Kubernetes manifests to current K8s context
	@echo -e "$(COLOR_GREEN)Deploying Lakehouse infrastructure to Kubernetes...$(COLOR_RESET)"
	kubectl apply -k k8s/base/

k8s-delete: ## Teardown all Kubernetes resources
	@echo -e "$(COLOR_YELLOW)Tearing down Kubernetes resources...$(COLOR_RESET)"
	kubectl delete -k k8s/base/
