#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head

echo "Seeding benchmarks..."
python scripts/seed_benchmarks.py

echo "Seeding watchlist..."
python scripts/seed_watchlist.py --skip-existing

echo "Starting uvicorn..."
exec uvicorn tradeagent.main:app --host 0.0.0.0 --port 8000
