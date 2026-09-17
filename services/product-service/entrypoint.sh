#!/bin/sh
set -e

echo "[product-service] aplicando migraciones..."
flask db upgrade

echo "[product-service] sembrando catálogo de ejemplo si está vacío..."
flask seed

echo "[product-service] iniciando gunicorn..."
exec gunicorn -b 0.0.0.0:5002 -w 2 --preload app:app
