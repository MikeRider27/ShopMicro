-- Ejecutar UNA VEZ contra el Postgres externo (192.168.11.220:5436) como user postgres:
--   psql -h 192.168.11.220 -p 5436 -U postgres -f init-db.sql
--
-- Crea una base de datos separada por microservicio (aislamiento lógico).
-- Las tablas dentro de cada base las crea el propio microservicio al arrancar
-- (SQLAlchemy db.create_all()).

SELECT 'CREATE DATABASE ecommerce_auth'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_auth')\gexec

SELECT 'CREATE DATABASE ecommerce_products'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_products')\gexec

SELECT 'CREATE DATABASE ecommerce_orders'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ecommerce_orders')\gexec
