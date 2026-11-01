# Task runner. Install: https://github.com/casey/just  (Windows: winget install --id Casey.Just -e)
# Every recipe is a plain `uv run ...` line, so it behaves the same in PowerShell and in sh.

set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

# List the available recipes.
default:
    @just --list

# Create the virtual environment and install runtime, dev and deck dependencies.
setup:
    uv sync --group dev --extra deck

# Run the test suite.
test:
    uv run pytest

# Lint with ruff.
lint:
    uv run ruff check

# Format the code base with ruff.
format:
    uv run ruff format

# Type-check with mypy (strict).
typecheck:
    uv run mypy

# Lint, type-check and test.
check: lint typecheck test

# Run the baseline experiment (ramp vs control) and print the summary.
simulate:
    uv run tipping simulate

# Run the sigma x duration x seed sweep and write results/sweep.parquet.
sweep:
    uv run tipping sweep

# Render the static figures in Spanish (deck) and English (README).
figures:
    uv run tipping figures --lang es
    uv run tipping figures --lang en

# Render the MP4 animations and poster frames.
animate:
    uv run tipping animate --lang es

# Build the slide deck into deck/build/.
deck:
    uv run python deck/build_deck.py

# Regenerate everything from scratch: simulation, sweep, figures, animations.
reproduce:
    uv run tipping reproduce

# Remove tool caches and generated outputs (data/, results/, deck/build/).
clean:
    uv run python -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('.mypy_cache', '.ruff_cache', '.pytest_cache', 'htmlcov', 'data', 'results', 'deck/build')]"
