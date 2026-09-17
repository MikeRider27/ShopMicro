#!/bin/sh
set -e

echo "[order-service] aplicando migraciones..."
flask db upgrade

echo "[order-service] iniciando gunicorn..."
exec gunicorn -b 0.0.0.0:5003 -w 2 --preload app:app
