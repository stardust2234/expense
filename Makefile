ORG ?= your-org
REPO ?= your-repo
MAIN_BRANCH ?= main
GIT_REMOTE ?= gitea
RENOVATE_ENDPOINT ?=
PYTHON ?= $(if $(wildcard $(CURDIR)/.venv/bin/python),$(CURDIR)/.venv/bin/python,python3)
GITEA_DIR ?= .gitea

SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
SETUP_SCRIPT ?= scripts/setup.sh
DOCKER_COMPOSE ?= docker compose
COMPOSE_FILE ?= infra/compose/docker-compose.yml
COMPOSE_ENV_FILE ?= $(CURDIR)/.env
COMPOSE_ENV_ARGS = $(if $(wildcard $(COMPOSE_ENV_FILE)),--env-file $(COMPOSE_ENV_FILE),)
BACKEND_ENV_ARGS = $(if $(wildcard $(COMPOSE_ENV_FILE)),--env-file ../.env,)

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install local dependencies
	@bash "$(SETUP_SCRIPT)"

ci-install: ## Install dependencies for CI without local hook setup
	@bash "$(SETUP_SCRIPT)" --ci

check: ## Run the standard local validation suite
	@$(MAKE) backend-format-check
	@$(MAKE) backend-lint
	@$(MAKE) backend-test
	@$(MAKE) database-check
	@$(MAKE) frontend-typecheck
	@$(MAKE) frontend-test
	@$(MAKE) frontend-build

up: ## Start the full stack in Docker Compose
	@$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS) -f $(COMPOSE_FILE) up --build

down: ## Stop the Docker Compose stack
	@$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS) -f $(COMPOSE_FILE) down

logs: ## Tail Docker Compose logs
	@$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS) -f $(COMPOSE_FILE) logs -f

ps: ## Show Docker Compose services
	@$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS) -f $(COMPOSE_FILE) ps

compose-build: ## Build all Docker Compose services
	@$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS) -f $(COMPOSE_FILE) build

smoke-test: ## Verify the full stack through Caddy and the API health endpoint
	@DOCKER_COMPOSE='$(DOCKER_COMPOSE) $(COMPOSE_ENV_ARGS)' COMPOSE_FILE='$(COMPOSE_FILE)' bash scripts/smoke-test.sh

backend-run: ## Start the FastAPI app locally
	@cd backend && $(PYTHON) -m uvicorn app.main:app --reload $(BACKEND_ENV_ARGS)

database-upgrade: ## Apply all pending database migrations
	@cd backend && set -a && if [[ -f ../.env ]]; then source ../.env; fi && set +a && $(PYTHON) -m alembic upgrade head

database-downgrade: ## Revert the most recent database migration
	@cd backend && set -a && if [[ -f ../.env ]]; then source ../.env; fi && set +a && $(PYTHON) -m alembic downgrade -1

database-seed: ## Add the default category taxonomy
	@cd backend && set -a && if [[ -f ../.env ]]; then source ../.env; fi && set +a && $(PYTHON) -m app.seed

database-check: ## Apply migrations to a clean SQLite database and detect model drift
	@MIGRATION_PYTHON="$(PYTHON)" bash scripts/check-migrations.sh

frontend-run: ## Start the Vite frontend locally
	@cd frontend && npm run dev

dev-certificate: ## Generate the local HTTPS certificate (set DEV_HOST for a specific LAN IP/name)
	@DEV_HOST="$(DEV_HOST)" bash scripts/create-dev-cert.sh

backend-lint: ## Run backend lint checks
	@cd backend && $(PYTHON) -m ruff check .

backend-format-check: ## Verify backend formatting without changing files
	@cd backend && $(PYTHON) -m ruff format --check .

backend-format: ## Format backend files
	@cd backend && $(PYTHON) -m ruff format .

backend-test: ## Run backend tests
	@cd backend && $(PYTHON) -m pytest

backend-audit: ## Audit installed Python dependencies in the local virtual environment
	@$(PYTHON) -m pip_audit --progress-spinner=off --skip-editable

frontend-typecheck: ## Run frontend TypeScript checks
	@cd frontend && npm run typecheck

frontend-test: ## Run frontend unit and routing tests
	@cd frontend && npm run test

frontend-build: ## Build the frontend bundle
	@cd frontend && npm run build

frontend-audit: ## Fail on high or critical npm vulnerabilities
	@cd frontend && npm audit --package-lock-only --audit-level=high

dependency-audit: ## Audit Python and JavaScript dependencies
	@$(MAKE) backend-audit
	@$(MAKE) frontend-audit

.PHONY: git-help branch-sync promote-main

git-help: ## Show branch workflow helper targets
	@echo "Git workflow targets:"
	@echo "  branch-sync   Sync main and development from $(GIT_REMOTE)"
	@echo "  promote-main  Merge development into main and push main to $(GIT_REMOTE)"

branch-sync: ## Sync main and development from the configured remote
	@git checkout main
	@git pull --ff-only $(GIT_REMOTE) main
	@git checkout development
	@git pull --ff-only $(GIT_REMOTE) development

promote-main: ## Merge development into main and push main to the configured remote
	@git checkout development
	@git pull --ff-only $(GIT_REMOTE) development
	@git checkout main
	@git pull --ff-only $(GIT_REMOTE) main
	@git merge --ff-only development
	@git push $(GIT_REMOTE) main

bootstrap-protection: ## Apply branch protection to the stable main branch after first release
	@RENOVATE_ENDPOINT="$(RENOVATE_ENDPOINT)" bash "$(GITEA_DIR)/scripts/apply-branch-protection.sh" --skip-missing "$(ORG)" "$(REPO)" "$(MAIN_BRANCH)"

