#!/bin/bash
set -e

echo "Running Alembic migrations..."
python -m alembic upgrade head

echo "Starting Uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
