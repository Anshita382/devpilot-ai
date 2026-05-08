# DevPilot AI — developer workflow
# macOS-friendly (uses python3). Run `make help` for the menu.

PYTHON := python3
VENV   := backend/.venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python
UVICORN:= $(VENV)/bin/uvicorn

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: setup
setup: ## Create the venv and install backend deps
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@echo "✓ backend ready. Next: make seed && make backend"

.PHONY: backend
backend: ## Run the FastAPI backend (mock mode) on :8000
	cd backend && DEVPILOT_MODE=mock .venv/bin/uvicorn app.main:app --reload --port 8000

.PHONY: seed
seed: ## Ingest the sample repo and run demo agent workflows
	cd backend && DEVPILOT_MODE=mock .venv/bin/python ../scripts/seed_demo.py

.PHONY: test
test: ## Run the backend test suite
	cd backend && .venv/bin/python -m pytest -q

.PHONY: eval
eval: ## Run the evaluation benchmark
	cd backend && DEVPILOT_MODE=mock .venv/bin/python -m eval.run_eval

.PHONY: frontend-setup
frontend-setup: ## Install frontend deps
	cd frontend && npm install

.PHONY: frontend
frontend: ## Run the Next.js dev server on :3000
	cd frontend && npm run dev

.PHONY: up
up: ## Bring up the full stack with docker compose
	docker compose up --build

.PHONY: down
down: ## Tear down the docker compose stack
	docker compose down -v

.PHONY: history
history: ## Build a realistic git commit history
	bash scripts/git_history.sh

.PHONY: clean
clean: ## Remove venv, caches, and local data
	rm -rf $(VENV) backend/.devpilot_data backend/.pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf frontend/.next frontend/node_modules
