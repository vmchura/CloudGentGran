# Catalunya Data Pipeline - Orchestration Makefile
# Provides convenient commands for development and deployment

.PHONY: help build up down logs test clean setup-dev setup-prod validate

# Default target
.DEFAULT_GOAL := help

# Variables
DOCKER_COMPOSE = docker-compose
AIRFLOW_UID ?= 50000

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "Catalunya Data Pipeline - Orchestration Commands"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "Examples:"
	@echo "  make setup-dev    # Set up for local development"
	@echo "  make up          # Start all services"
	@echo "  make logs        # View logs"
	@echo "  make test        # Run tests"

build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	$(DOCKER_COMPOSE) build

up: ## Start all services in background
	@echo "$(BLUE)Starting Catalunya Data Pipeline services...$(NC)"
	@echo "Setting AIRFLOW_UID to $(AIRFLOW_UID)"
	AIRFLOW_UID=$(AIRFLOW_UID) $(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)Services started!$(NC)"
	@echo "Airflow UI will be available at: http://localhost:8080"
	@echo "Default credentials: airflow/airflow"

up-build: ## Build and start all services
	@echo "$(BLUE)Building and starting Catalunya Data Pipeline services...$(NC)"
	AIRFLOW_UID=$(AIRFLOW_UID) $(DOCKER_COMPOSE) up --build -d
	@echo "$(GREEN)Services started!$(NC)"

up-fg: ## Start all services in foreground
	@echo "$(BLUE)Starting Catalunya Data Pipeline services in foreground...$(NC)"
	AIRFLOW_UID=$(AIRFLOW_UID) $(DOCKER_COMPOSE) up

down: ## Stop all services
	@echo "$(YELLOW)Stopping Catalunya Data Pipeline services...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)Services stopped!$(NC)"

down-volumes: ## Stop all services and remove volumes
	@echo "$(YELLOW)Stopping services and removing volumes...$(NC)"
	$(DOCKER_COMPOSE) down -v
	@echo "$(GREEN)Services stopped and volumes removed!$(NC)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting Catalunya Data Pipeline services...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)Services restarted!$(NC)"

logs: ## View logs from all services
	$(DOCKER_COMPOSE) logs -f

logs-airflow: ## View Airflow webserver logs
	$(DOCKER_COMPOSE) logs -f airflow-webserver

logs-scheduler: ## View Airflow scheduler logs
	$(DOCKER_COMPOSE) logs -f airflow-scheduler

logs-postgres: ## View PostgreSQL logs
	$(DOCKER_COMPOSE) logs -f postgres

status: ## Show service status
	@echo "$(BLUE)Service Status:$(NC)"
	$(DOCKER_COMPOSE) ps

shell: ## Open bash shell in Airflow webserver container
	$(DOCKER_COMPOSE) exec airflow-webserver bash

shell-scheduler: ## Open bash shell in Airflow scheduler container
	$(DOCKER_COMPOSE) exec airflow-scheduler bash

dbt-shell: ## Open DBT shell for development
	$(DOCKER_COMPOSE) exec airflow-webserver bash -c "cd /opt/airflow/dbt_mart && bash"

test: ## Run orchestration tests
	@echo "$(BLUE)Running orchestration tests...$(NC)"
	$(DOCKER_COMPOSE) exec airflow-webserver python -m pytest /opt/airflow/tests/ -v
	@echo "$(GREEN)Tests completed!$(NC)"

test-dbt: ## Test DBT connection and models
	@echo "$(BLUE)Testing DBT setup...$(NC)"
	$(DOCKER_COMPOSE) exec airflow-webserver bash /opt/airflow/dbt_project/scripts/setup_dbt.sh --test-only
	@echo "$(GREEN)DBT tests completed!$(NC)"

validate: ## Validate DAGs and configuration
	@echo "$(BLUE)Validating Airflow DAGs...$(NC)"
	$(DOCKER_COMPOSE) exec airflow-webserver airflow dags list
	$(DOCKER_COMPOSE) exec airflow-webserver python -c "from airflow.models import DagBag; db = DagBag(); print('✅ DAG validation passed' if len(db.import_errors) == 0 else '❌ DAG validation failed'); [print(f'Error in {k}: {v}') for k, v in db.import_errors.items()]"
	@echo "$(GREEN)Validation completed!$(NC)"

setup-dev: ## Set up development environment
	@echo "$(BLUE)Setting up development environment...$(NC)"
	@echo "Creating necessary directories..."
	@mkdir -p airflow/dags airflow/logs airflow/plugins
	@mkdir -p dbt/profiles dbt/scripts
	@mkdir -p docker config/environment tests
	@echo "$(GREEN)Development environment setup completed!$(NC)"
	@echo "Next steps:"
	@echo "1. Run 'make up-build' to start services"
	@echo "2. Wait for services to be healthy"
	@echo "3. Visit http://localhost:8080 (airflow/airflow)"

setup-prod: ## Set up production environment
	@echo "$(BLUE)Setting up production environment...$(NC)"
	@echo "$(YELLOW)Production setup requires additional configuration:$(NC)"
	@echo "1. Set up proper AWS credentials"
	@echo "2. Configure production environment variables"
	@echo "3. Set up external PostgreSQL database"
	@echo "4. Configure S3 for remote logging"
	@echo "See documentation for detailed production setup."

init-airflow: ## Initialize Airflow (run after first startup)
	@echo "$(BLUE)Initializing Airflow...$(NC)"
	$(DOCKER_COMPOSE) exec airflow-webserver airflow db init
	$(DOCKER_COMPOSE) exec airflow-webserver airflow users create \
		--username airflow \
		--firstname Catalunya \
		--lastname Admin \
		--role Admin \
		--email admin@catalunya-data.org \
		--password airflow
	@echo "$(GREEN)Airflow initialized!$(NC)"

clean: ## Clean up containers, images, and volumes
	@echo "$(YELLOW)Cleaning up Docker resources...$(NC)"
	$(DOCKER_COMPOSE) down -v --rmi local --remove-orphans
	@docker system prune -f
	@echo "$(GREEN)Cleanup completed!$(NC)"

clean-logs: ## Clean log files
	@echo "$(YELLOW)Cleaning log files...$(NC)"
	@rm -rf airflow/logs/*
	@echo "$(GREEN)Log files cleaned!$(NC)"

health-check: ## Check health of all services
	@echo "$(BLUE)Checking service health...$(NC)"
	@echo "Airflow Webserver:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health || echo "Not responding"
	@echo ""
	@echo "PostgreSQL:"
	@$(DOCKER_COMPOSE) exec postgres pg_isready -U airflow || echo "Not ready"
	@echo "$(GREEN)Health check completed!$(NC)"

backup-db: ## Backup PostgreSQL database
	@echo "$(BLUE)Backing up PostgreSQL database...$(NC)"
	@$(DOCKER_COMPOSE) exec postgres pg_dump -U airflow airflow > airflow_backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Database backup completed!$(NC)"

restore-db: ## Restore PostgreSQL database (requires BACKUP_FILE variable)
	@echo "$(BLUE)Restoring PostgreSQL database...$(NC)"
	@if [ -z "$(BACKUP_FILE)" ]; then \
		echo "$(RED)Error: BACKUP_FILE variable is required$(NC)"; \
		echo "Usage: make restore-db BACKUP_FILE=backup.sql"; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE) exec -T postgres psql -U airflow -d airflow < $(BACKUP_FILE)
	@echo "$(GREEN)Database restore completed!$(NC)"

monitor: ## Show real-time resource usage
	@echo "$(BLUE)Monitoring resource usage (Ctrl+C to stop)...$(NC)"
	@watch 'docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" --no-stream | grep orchestra'

# Development shortcuts
dev: setup-dev up-build ## Quick development setup

dev-logs: ## Follow development logs
	$(DOCKER_COMPOSE) logs -f airflow-webserver airflow-scheduler

dev-reset: down-volumes clean setup-dev up-build ## Reset development environment completely

# Production shortcuts
prod-deploy: ## Deploy to production (placeholder)
	@echo "$(YELLOW)Production deployment should be handled by CI/CD pipeline$(NC)"
	@echo "This is a placeholder for production deployment logic"

prod-status: ## Check production status (placeholder)
	@echo "$(BLUE)Production status check$(NC)"
	@echo "Implement production-specific health checks here"