#!/bin/sh
set -e

# Si se pasan argumentos al contenedor (worker, beat), ejecutarlos directamente.
# Solo el backend (sin argumentos) ejecuta las migraciones.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "==> Esperando base de datos..."
sleep 2

# Restringir permisos de archivos sensibles en el volumen storage
chmod 700 /app/storage 2>/dev/null || true
find /app/storage -name "*.json" -exec chmod 600 {} \; 2>/dev/null || true
find /app/storage -name "*.db"   -exec chmod 600 {} \; 2>/dev/null || true

echo "==> Ejecutando migraciones Alembic..."
alembic upgrade head

echo "==> Iniciando servidor FastAPI..."
# Producción: SIN --reload. Así el servidor es PID 1; si el kernel lo mata por
# OOM, el contenedor sale y `restart: unless-stopped` lo levanta solo (auto-heal).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
