#!/usr/bin/env bash
set -euo pipefail

: "${PORT:=8080}"
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-command_center.settings}

echo "=== ENTRYPOINT: Starting Django App with External DB (Neon) ==="

echo "Running Django migrations..."
python manage.py migrate --noinput || echo "Migration skipped or already done."

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting background task (run_quote_scanner)..."
python manage.py run_quote_scanner &

echo "Starting Gunicorn on 0.0.0.0:${PORT} ..."
exec gunicorn command_center.wsgi:application \
    --bind 0.0.0.0:${PORT} \
    --workers 2 \
    --threads 4 \
    --timeout 0
