#!/bin/sh
set -e

# Si se pasan argumentos al contenedor (worker, beat), ejecutarlos directamente.
# Solo el backend (sin argumentos) ejecuta las migraciones.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Esperando base de datos..."
sleep 2

echo "==> Ejecutando migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando servidor FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
