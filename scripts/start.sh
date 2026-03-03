#!/usr/bin/env bash
set -euo pipefail

echo "Running database migrations..."
alembic upgrade head

# Verify tables were actually created (guards against partial init)
TABLE_COUNT=$(python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute(\"SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='stock'\")
print(cur.fetchone()[0])
conn.close()
")

if [ "$TABLE_COUNT" -eq 0 ]; then
    echo "WARNING: Migration recorded but tables missing. Re-running..."
    python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()
cur.execute('DELETE FROM alembic_version')
conn.commit()
conn.close()
"
    alembic upgrade head
fi

echo "Seeding benchmarks..."
python scripts/seed_benchmarks.py

echo "Seeding watchlist..."
python scripts/seed_watchlist.py --skip-existing

echo "Starting uvicorn..."
exec uvicorn tradeagent.main:app --host 0.0.0.0 --port 8000
