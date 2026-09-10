#!/usr/bin/env bash
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -q 2>/dev/null; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Running Alembic migrations..."
alembic upgrade head

echo "Starting FastAPI..."
# Single worker for local/dev. NOTE (Phase L): a multi-worker startup races
# the idempotent permission/role seed (unique constraint on permissions.code)
# AND breaks the single-process in-memory rate limiter + WebSocket manager.
# Scale out only after moving those to Redis / an external store.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
