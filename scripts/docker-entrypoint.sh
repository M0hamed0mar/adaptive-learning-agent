#!/bin/sh
# ============================================================
# Docker entrypoint for the Adaptive Learning Agent.
#
# Responsibilities:
#   1. Ensure the data directory exists.
#   2. Apply Alembic migrations.
#   3. Start uvicorn.
# ============================================================

set -e

echo "[entrypoint] Starting Adaptive Learning Agent"
echo "[entrypoint] APP_ENV=${APP_ENV:-development}"
echo "[entrypoint] PORT=${PORT:-8000}"
echo "[entrypoint] DATABASE_URL=${DATABASE_URL}"

# --- Ensure the data directory exists (SQLite) ---
mkdir -p /app/data

# --- Apply database migrations ---
echo "[entrypoint] Applying database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations applied."

# --- Start the application ---
echo "[entrypoint] Starting uvicorn on 0.0.0.0:${PORT:-8000}"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers 1 \
    --proxy-headers \
    --forwarded-allow-ips="*" \
    --log-level "${LOG_LEVEL_LOWER:-info}"
