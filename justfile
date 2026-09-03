# lynkeus development tasks

# Show available commands
default:
    @just --list

# Install the locked environment with every dependency group
sync:
    uv sync --all-groups

# Run the test suite (the database-free tier)
test:
    uv run pytest -m "not integration"

# Run every test, including the tier that needs `just db-up`
test-all:
    LYNKEUS_TEST_DSN="${LYNKEUS_TEST_DSN:-postgresql://lynkeus:lynkeus@127.0.0.1:${LYNKEUS_PG_PORT:-11401}/lynkeus_test}" \
        uv run pytest

# Start the disposable PostgreSQL the integration tier needs
db-up:
    @just _compose up -d --wait postgres

# Stop it and discard its data
db-down:
    @just _compose down -v

# `docker compose` (plugin) where it exists, `docker-compose` (standalone) otherwise
_compose *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    if docker compose version >/dev/null 2>&1; then
        exec docker compose {{ARGS}}
    elif command -v docker-compose >/dev/null 2>&1; then
        exec docker-compose {{ARGS}}
    fi
    echo "Neither 'docker compose' nor 'docker-compose' is available." >&2
    echo "Install Docker Compose, or point LYNKEUS_TEST_DSN at your own PostgreSQL." >&2
    exit 1

# Lint with ruff
lint:
    uv run ruff check

# Format with ruff (Python, and the Python blocks inside Markdown)
fmt:
    uv run ruff format

# Fail if anything is unformatted — the same gate CI applies
fmt-check:
    uv run ruff format --check

# Type-check with basedpyright
typecheck:
    uv run basedpyright

# Lint, type-check and test
check: lint fmt-check typecheck test
