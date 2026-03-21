#!/usr/bin/env bash
set -o errexit

pip install --no-cache-dir .

# Run database migrations
alembic upgrade head

# Seed demo data (idempotent — skips if already seeded)
python -m scripts.seed_demo
