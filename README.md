# Cars24 vs Spinny Competitive Intel

Multi-agent extraction + ranking pipeline for an assessment task.
See `docs/superpowers/specs/2026-05-06-cars24-spinny-comp-intel-design.md`.

## Setup

    uv sync
    cp .env.example .env  # add ANTHROPIC_API_KEY

## Run

    uv run python scripts/collect_snapshots.py   # one-time, manual
    uv run python scripts/run_pipeline.py        # end-to-end on ranking 6
    uv run python scripts/run_evals.py           # E2-E5 over gold

## Test

    uv run pytest
