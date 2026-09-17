#!/bin/sh
set -e

echo "[auth-service] aplicando migraciones..."
flask db upgrade

echo "[auth-service] iniciando gunicorn..."
exec gunicorn -b 0.0.0.0:5001 -w 2 --preload app:app
