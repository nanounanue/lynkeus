# lynkeus development tasks

# Show available commands
default:
    @just --list

# Install the locked environment with every dependency group
sync:
    uv sync --all-groups

# Run the test suite
test:
    uv run pytest

# Lint with ruff
lint:
    uv run ruff check

# Format with ruff
fmt:
    uv run ruff format

# Type-check with basedpyright
typecheck:
    uv run basedpyright

# Lint, type-check and test
check: lint typecheck test
