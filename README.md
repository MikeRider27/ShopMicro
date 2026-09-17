# ShopMicro — E-commerce con Next.js + microservicios Flask

![CI](https://github.com/MikeRider27/ShopMicro/actions/workflows/ci.yml/badge.svg)

Arquitectura:

```
frontend (Next.js, :3000)
   │
   ▼
gateway (Nginx, :8080)  ──/api/auth/──▶ auth-service (Flask, :5001) ─┐
                          ──/api/products/──▶ product-service (Flask, :5002) ─┼──▶ Postgres (:5432, 1 base por servicio)
                          ──/api/orders/──▶ order-service (Flask, :5003) ─┘        + Redis (:6379, rate limiting)
                                              └──▶ product-service (reserva de stock)
```

- **auth-service**: registro/login de usuarios, emite JWT (`ecommerce_auth`).
- **product-service**: catálogo de productos y categorías, con seed de datos de ejemplo (`ecommerce_products`).
- **order-service**: crea pedidos validando y descontando stock vía `product-service`, protegido con JWT (`ecommerce_orders`).
- **gateway**: Nginx enruta `/api/*` a cada microservicio.
- **frontend**: catálogo, carrito (persistido en localStorage), login/registro, checkout e historial de pedidos.
- **postgres**: contenedor incluido con volumen persistente; el proyecto no depende de ningún servidor externo para funcionar (ver [docs/adr](docs) si se agregan ADRs más adelante).
- **redis**: backend compartido del rate limiting (necesario porque cada servicio corre con 2 workers de gunicorn).

## 1. Variables de entorno (obligatorias)

Los microservicios **se niegan a arrancar** si falta alguna variable sensible (fail-fast), en vez de usar valores por defecto inseguros. Copiá el template y completá los valores marcados como obligatorios:

```bash
cp .env.example .env
```

Generá secretos fuertes para `JWT_SECRET_KEY` y `ADMIN_API_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Por defecto todo corre contenido en Docker (Postgres y Redis incluidos), sin depender de ninguna IP externa. Si preferís usar un Postgres propio ya existente, cambiá `POSTGRES_HOST`/`POSTGRES_PORT` en `.env`, quitá el servicio `postgres` (y sus `depends_on: condition: service_healthy`) de `docker-compose.yml`, y corré `init-db.sql` contra ese servidor una vez.

## 2. Levantar todo con Docker

```bash
docker compose up --build
```

Postgres crea automáticamente las 3 bases de datos la primera vez que arranca (`docker/postgres-initdb/01-create-databases.sh`). Cada microservicio aplica sus propias migraciones al iniciar (`flask db upgrade`, ver [Migraciones](#migraciones)); `product-service` además siembra un catálogo de ejemplo si está vacío (`flask seed`).

- Frontend: http://localhost:3000
- Gateway (API): http://localhost:8080/api/...

## Endpoints principales

| Servicio | Método | Ruta (vía gateway) | Descripción |
|---|---|---|---|
| auth | POST | `/api/auth/register` | Crear cuenta |
| auth | POST | `/api/auth/login` | Login, devuelve JWT |
| auth | GET | `/api/auth/me` | Usuario autenticado |
| products | GET | `/api/products/products` | Listar productos (`?category=&search=`) |
| products | GET | `/api/products/products/<id>` | Detalle de producto |
| products | GET | `/api/products/categories` | Listar categorías |
| products | POST/PUT/DELETE | `/api/products/products` | Admin (header `X-Admin-Key`, ver `ADMIN_API_KEY`) |
| orders | POST | `/api/orders/orders` | Crear pedido (requiere JWT y header `Idempotency-Key`) |
| orders | GET | `/api/orders/orders` | Historial del usuario autenticado |

## Datos de demo adicionales

`scripts/seed_demo_data.py` agrega más productos, 3 usuarios de prueba y pedidos de ejemplo, llamando a la API (no toca la base de datos directamente):

```bash
python3 scripts/seed_demo_data.py
# o, si usas puertos/host distintos:
GATEWAY_URL=http://localhost:8080 ADMIN_API_KEY=tu-admin-key python3 scripts/seed_demo_data.py
```

Usuarios creados: `ana@example.com`, `carlos@example.com`, `maria@example.com` (contraseña `demo1234`).

## Migraciones

Cada microservicio usa Flask-Migrate/Alembic (carpeta `migrations/`) en vez de `db.create_all()`. El `entrypoint.sh` de cada contenedor corre `flask db upgrade` automáticamente antes de levantar gunicorn, así que con `docker compose up` no hay que hacer nada manual.

Para cambiar el esquema de un servicio (ejemplo con `product-service`):

```bash
cd services/product-service

# 1. Modificar los modelos en models.py

# 2. Generar la migración contra una base con el esquema actual
#    (podés usar el Postgres de docker-compose: docker compose up -d postgres)
FLASK_APP=app.py POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
  POSTGRES_USER=... POSTGRES_PASSWORD=... POSTGRES_DB=ecommerce_products \
  CORS_ALLOWED_ORIGINS=http://localhost:3000 ADMIN_API_KEY=... \
  flask db migrate -m "descripción del cambio"

# 3. Revisar el archivo generado en migrations/versions/ (Alembic no siempre
#    acierta con renombres o cambios de tipo) y aplicarla
flask db upgrade

# Revertir la última migración si algo salió mal:
flask db downgrade -1
```

En producción, el `entrypoint.sh` de cada servicio aplica las migraciones pendientes automáticamente al arrancar el contenedor.

## Tests

Cada microservicio tiene su propia suite de pytest (SQLite en memoria, sin depender de Postgres real) con cobertura mínima exigida del 70%:

```bash
cd services/auth-service   # o product-service / order-service
pip install -r requirements-dev.txt
ruff check .
python -m pytest
```

También hay una prueba de integración real (`tests/integration/test_end_to_end.py`) que ejercita el flujo completo auth → order → product → reserva de stock contra el stack ya desplegado:

```bash
docker compose up -d
pip install pytest requests
GATEWAY_URL=http://localhost:8080 python -m pytest tests/integration -v
```

## CI/CD

`.github/workflows/ci.yml` corre en cada push/PR a `main`:
- **backend-tests**: lint (`ruff`) + `pytest` con cobertura para los 3 microservicios (matriz).
- **docker-build**: construye todas las imágenes con `docker compose build` para detectar errores de build temprano.

## Seguridad

- Ningún secreto tiene valor por defecto en el código: `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `ADMIN_API_KEY`, `CORS_ALLOWED_ORIGINS` y `REDIS_URL` son obligatorios; si falta alguno, el servicio no arranca.
- CORS restringido a los orígenes listados en `CORS_ALLOWED_ORIGINS` (no `*`).
- Rate limiting (Flask-Limiter + Redis) en `/register`, `/login` (10/min) y en los endpoints de administración de productos (20/min). Redis es necesario porque cada servicio corre con 2 workers de gunicorn y un límite en memoria no sería consistente entre procesos.
- JWT con expiración configurable (`JWT_ACCESS_TOKEN_EXPIRES_MINUTES`, default 60 min). Se evaluó agregar refresh tokens; se dejó fuera de este alcance por simplicidad — el frontend simplemente pide login de nuevo cuando el token expira (ver manejo de 401 en `frontend/lib/api.ts`).

## Consistencia entre order-service y product-service

`order-service` no comparte base de datos con `product-service` (cada uno tiene la suya), así que crear un pedido implica una operación distribuida en dos pasos: reservar stock allá, guardar el pedido acá. Sin cuidado extra eso puede dejar inconsistencias, así que:

- **Idempotencia:** `POST /orders` exige un header `Idempotency-Key` (el frontend genera un UUID por intento de compra, ver `frontend/app/checkout/page.tsx`). Si dos requests llegan con la misma key (reintento de red, doble click), la segunda devuelve el pedido ya creado (`200`) en vez de reservar stock y cobrar dos veces.
- **Compensación:** si `product-service` ya descontó el stock pero `order-service` falla al guardar el pedido (DB caída, excepción inesperada), se llama a `POST /internal/release-stock` para devolver esa reserva antes de responder el error. Es *best-effort*: si esa llamada de compensación también falla, se loguea y el inventario queda inconsistente hasta una reconciliación manual — no hay reintentos automáticos ni cola de compensación pendiente todavía.
- **Por qué no arquitectura orientada a eventos:** un bus de eventos (outbox + broker) daría garantías más fuertes (reintentos, at-least-once, auditoría), pero suma un componente de infraestructura más, consistencia eventual en la UI, y complejidad operativa que no se justifica en este tamaño de proyecto. La combinación reserva síncrona + Idempotency-Key + compensación cubre los casos reales (reintento del cliente, caída puntual de un servicio) con mucho menos costo. Si el sistema creciera a más microservicios o necesitara desacoplar mejor los fallos, valdría la pena reevaluarlo.

## Notas de diseño / simplificaciones

- Cada microservicio usa su propia base de datos dentro del mismo Postgres (aislamiento lógico, sin compartir tablas).
- La escritura del catálogo (`POST/PUT/DELETE /products`) está protegida por un header simple `X-Admin-Key` (variable `ADMIN_API_KEY`), pensado para administración interna, no para el frontend público.
- El carrito de compras vive en el cliente (localStorage), no hay carrito persistido en base de datos.

## Roadmap

Mejoras identificadas y no incluidas todavía en este alcance: validación estructurada de requests (Marshmallow/Pydantic), manejo de errores global consistente, correlation IDs y métricas, hardening adicional de Docker (usuario no root), pruebas E2E de frontend, documentación OpenAPI/Swagger, ADRs, y plantillas de GitHub (PR/Issues/CONTRIBUTING/SECURITY).

------------------------------------------------------------------------

# 👤 Autor

-   **Miguel Villalba**
-   📧 mike.mavc27@gmail.com

------------------------------------------------------------------------

# 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo
[LICENSE](LICENSE) para más detalles.