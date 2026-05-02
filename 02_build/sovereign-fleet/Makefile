# OpenClaw Sovereign Fleet — Makefile
# One command to rule them all.
# Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a

.PHONY: help setup up down logs status health build clean validate-policies

COMPOSE = docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-24s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────

setup: ## First-time setup: copy env, create workspaces, build images
	@echo "Setting up Sovereign Fleet..."
	@test -f .env || (cp .env.template .env && echo "  .env created — edit with your keys")
	@mkdir -p ../Entity_Kimmy ../Entity_Alpha ../Entity_Charlie
	@echo "  Workspace directories created"
	$(COMPOSE) build
	@echo "  Docker images built"
	@echo ""
	@echo "Fleet ready. Edit .env then run: make up"
	@echo "  Traefik dashboard: http://localhost:8181"
	@echo "  Kimmy:   http://kimmy.internal (or localhost:8180)"
	@echo "  Alpha:   http://alpha.internal"
	@echo "  Charlie: http://charlie.internal"

# ── Docker ───────────────────────────────────────────────────────

up: ## Start all fleet services
	$(COMPOSE) up -d

down: ## Stop all fleet services
	$(COMPOSE) down

logs: ## Tail all fleet logs
	$(COMPOSE) logs -f

logs-kimmy: ## Tail Kimmy logs
	$(COMPOSE) logs -f entity_kimmy

logs-alpha: ## Tail Alpha logs
	$(COMPOSE) logs -f entity_alpha

logs-charlie: ## Tail Charlie logs
	$(COMPOSE) logs -f entity_charlie

build: ## Rebuild agent images
	$(COMPOSE) build

rebuild: ## Force rebuild and restart all entities
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

# ── Status & Health ──────────────────────────────────────────────

status: ## Show container status
	$(COMPOSE) ps

health: ## Check health of all entities
	@echo "--- Kimmy (Orchestrator) ---"
	@curl -s http://localhost:8180/health -H "Host: kimmy.internal" 2>/dev/null | python3 -m json.tool || echo "  unreachable"
	@echo ""
	@echo "--- Alpha (Arbiter) ---"
	@curl -s http://localhost:8180/health -H "Host: alpha.internal" 2>/dev/null | python3 -m json.tool || echo "  unreachable"
	@echo ""
	@echo "--- Charlie (Plumber) ---"
	@curl -s http://localhost:8180/health -H "Host: charlie.internal" 2>/dev/null | python3 -m json.tool || echo "  unreachable"

identity: ## Show identity of all entities
	@for entity in kimmy alpha charlie; do \
		echo "--- $$entity ---"; \
		curl -s http://localhost:8180/identity -H "Host: $$entity.internal" 2>/dev/null | python3 -m json.tool || echo "  unreachable"; \
		echo ""; \
	done

# ── Policy ───────────────────────────────────────────────────────

validate-policies: ## Validate Cedar policy syntax
	@echo "Validating Cedar policies..."
	@python3 scripts/validate-policies.py policies/
	@echo "Policies valid."

# ── Testing ──────────────────────────────────────────────────────

test: ## Run agent tests
	cd agent && pip install -e ".[dev]" -q && python -m pytest tests/ -v

lint: ## Lint agent code
	cd agent && pip install ruff -q && ruff check src/ && ruff format --check src/

# ── Cleanup ──────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	find agent -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find agent -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find agent -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
