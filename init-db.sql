-- NOTA: desde que docker-compose.yml incluye su propio contenedor de Postgres,
-- este script YA NO hace falta para el flujo por defecto (las bases se crean
-- automáticamente vía docker/postgres-initdb/01-create-databases.sh la primera
-- vez que arranca ese contenedor).
--
-- Este script queda solo para quien prefiera usar un Postgres externo/propio en
-- vez del contenedor incluido. Ejecutar UNA VEZ contra ese servidor:
--   psql -h <host> -p <puerto> -U <usuario> -f init-db.sql
--
-- Las tablas dentro de cada base las crea el propio microservicio al arrancar
-- (SQLAlchemy db.create_all()).

SELECT 'CREATE DATABASE ecommerce_auth'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_auth')\gexec

SELECT 'CREATE DATABASE ecommerce_products'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_products')\gexec

SELECT 'CREATE DATABASE ecommerce_orders'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_orders')\gexec
