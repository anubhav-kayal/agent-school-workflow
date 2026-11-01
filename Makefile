.DEFAULT_GOAL := help
UV ?= uv
RUN := $(UV) run

.PHONY: help install up down test lint fmt typecheck migrate seed evals run worker demo

help: ## Show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install: ## Install dependencies into .venv
	$(UV) sync

up: ## Start Postgres and Redis and wait until healthy
	docker compose up -d --wait

down: ## Stop local services
	docker compose down

test: install ## Run the test suite
	$(RUN) pytest -q

lint: install ## Ruff lint + format check + mypy
	$(RUN) ruff check .
	$(RUN) ruff format --check .
	$(RUN) mypy app evals

fmt: ## Auto-format and fix lint
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

migrate: ## Apply database migrations
	@if [ -f alembic.ini ]; then $(RUN) alembic upgrade head; \
	else echo "migrations arrive in M1"; fi

seed: ## Load fake demo data
	@if [ -f app/seed.py ]; then $(RUN) python -m app.seed; \
	else echo "seed arrives in M1"; fi

evals: ## Run LLM evals (calls the real Claude API; never in CI)
	@if [ -f evals/runner.py ]; then $(RUN) python -m evals.runner --tier $${TIER:-tier_fast}; \
	else echo "evals arrive in M2"; fi

run: ## Start the API with autoreload
	$(RUN) uvicorn app.main:app --reload --port 8000

worker: ## Start the arq background worker
	@if [ -f app/jobs/worker.py ]; then $(RUN) arq app.jobs.worker.WorkerSettings; \
	else echo "worker arrives in M2"; fi

demo: up install ## One command: services, migrations, seed, then the demo at /demo/chat
	$(RUN) alembic upgrade head
	$(RUN) python -m app.seed
	@echo "\n  Demo: http://localhost:8000/demo/chat  (needs OPENAI_API_KEY in .env)\n"
	DEMO_MODE=true $(RUN) uvicorn app.main:app --port 8000
