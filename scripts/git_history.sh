#!/usr/bin/env bash
#
# Build a realistic commit history for the DevPilot AI repo.
#
# Run from the repository root AFTER reviewing the code:
#   bash scripts/git_history.sh
#
# This stages files in logical groups and commits them with messages that read
# like an actual build progression. It does NOT push; review with `git log`
# then `git push -u origin main` yourself.
#
set -euo pipefail

if [ ! -d backend/app ]; then
  echo "error: run this from the repository root (backend/app not found)" >&2
  exit 1
fi

git init -q 2>/dev/null || true
git config user.name  "$(git config user.name  || echo 'Anshita')" >/dev/null 2>&1 || true

commit() {
  local msg="$1"; shift
  git add "$@" 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git commit -q -m "$msg"
    echo "  ✓ $msg"
  fi
}

echo "Building commit history..."

commit "chore: project scaffolding, gitignore, license" \
  .gitignore LICENSE README.md Makefile .env.example

commit "feat(db): SQLAlchemy models and session with SQLite/Postgres fallback" \
  backend/app/__init__.py backend/app/config.py backend/app/db

commit "feat(rag): AST-aware chunker, hybrid embeddings, BM25, retriever" \
  backend/app/rag

commit "feat(mcp): tool server with file/git/search/lint tools" \
  backend/app/mcp

commit "feat(sandbox): project detection and sandboxed test runner" \
  backend/app/sandbox

commit "feat(llm): provider client (mock/ollama/api) and prompts" \
  backend/app/llm

commit "feat(agents): planner, retrieval, coder, tester, reviewer, evaluator" \
  backend/app/agents/state.py backend/app/agents/planner.py \
  backend/app/agents/retrieval.py backend/app/agents/coder.py \
  backend/app/agents/tester.py backend/app/agents/reviewer.py \
  backend/app/agents/evaluator.py backend/app/agents/__init__.py

commit "feat(agents): LangGraph workflow with self-healing repair loop" \
  backend/app/agents/graph.py

commit "feat(telemetry): Prometheus metrics" \
  backend/app/telemetry

commit "feat(api): repos, chat, agents, and metrics routes" \
  backend/app/schemas backend/app/api backend/app/main.py

commit "test: backend suite (rag, chunker, mcp, agents, api, self-heal)" \
  backend/tests backend/pytest.ini

commit "feat(eval): reproducible evaluation harness" \
  backend/eval

commit "chore: requirements" \
  backend/requirements.txt

commit "feat(examples): sample FastAPI and Node target repos" \
  examples

commit "feat(frontend): Next.js dashboard, repos, run timeline, settings" \
  frontend

commit "feat(infra): docker-compose, Dockerfiles, Prometheus, Grafana" \
  docker-compose.yml backend/Dockerfile frontend/Dockerfile infra

commit "docs: architecture, agent workflow, RAG design, evaluation" \
  docs scripts

# Catch anything not explicitly grouped above.
commit "chore: remaining project files" .

echo ""
echo "Done. Review with: git log --oneline"
echo "Then: git branch -M main && git remote add origin <url> && git push -u origin main"
