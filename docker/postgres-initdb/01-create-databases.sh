#!/bin/bash
# Se ejecuta automáticamente la primera vez que arranca el contenedor de Postgres
# (solo si el volumen de datos está vacío). Crea una base de datos por
# microservicio para mantener el aislamiento lógico entre ellos.
#
# Si cambias los nombres de base de datos en .env (AUTH_DB_NAME, etc.), actualiza
# también esta lista.
set -euo pipefail

DATABASES=("ecommerce_auth" "ecommerce_products" "ecommerce_orders")

for db in "${DATABASES[@]}"; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    SELECT 'CREATE DATABASE "$db"'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db')\gexec
EOSQL
done
