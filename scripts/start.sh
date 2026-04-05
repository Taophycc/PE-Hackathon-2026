#!/bin/bash
set -e

echo "Running DB migrations..."
uv run python scripts/init_db.py

echo "Starting gunicorn..."
exec uv run gunicorn -w 8 --timeout 120 -b 0.0.0.0:8000 run:app
