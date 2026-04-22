#!/bin/sh
set -e

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Esperando base de datos..."
sleep 2

echo "==> Ejecutando migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando servidor FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
