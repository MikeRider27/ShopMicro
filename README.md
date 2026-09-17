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

Postgres crea automáticamente las 3 bases de datos la primera vez que arranca (`docker/postgres-initdb/01-create-databases.sh`), y cada microservicio crea sus propias tablas al iniciar (`db.create_all()`); `product-service` además siembra un catálogo de ejemplo si está vacío.

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
| orders | POST | `/api/orders/orders` | Crear pedido (requiere JWT) |
| orders | GET | `/api/orders/orders` | Historial del usuario autenticado |

## Datos de demo adicionales

`scripts/seed_demo_data.py` agrega más productos, 3 usuarios de prueba y pedidos de ejemplo, llamando a la API (no toca la base de datos directamente):

```bash
python3 scripts/seed_demo_data.py
# o, si usas puertos/host distintos:
GATEWAY_URL=http://localhost:8080 ADMIN_API_KEY=tu-admin-key python3 scripts/seed_demo_data.py
```

Usuarios creados: `ana@example.com`, `carlos@example.com`, `maria@example.com` (contraseña `demo1234`).

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

## Notas de diseño / simplificaciones

- Cada microservicio usa su propia base de datos dentro del mismo Postgres (aislamiento lógico, sin compartir tablas).
- `order-service` llama a `product-service` (`/internal/reserve-stock`) para validar y descontar stock de forma síncrona al crear un pedido. **Limitación conocida:** si `order-service` falla al guardar el pedido después de que `product-service` ya descontó el stock, el stock no se libera automáticamente (no hay compensación/saga todavía) — queda documentado como mejora pendiente.
- La escritura del catálogo (`POST/PUT/DELETE /products`) está protegida por un header simple `X-Admin-Key` (variable `ADMIN_API_KEY`), pensado para administración interna, no para el frontend público.
- El carrito de compras vive en el cliente (localStorage), no hay carrito persistido en base de datos.
- Las tablas se crean con `db.create_all()` en vez de migraciones versionadas (Alembic/Flask-Migrate); es una limitación conocida para evolucionar el esquema en producción.

## Roadmap

Mejoras identificadas y no incluidas todavía en este alcance: migraciones con Alembic, idempotencia y compensación de stock, validación estructurada de requests (Marshmallow/Pydantic), manejo de errores global consistente, correlation IDs y métricas, hardening adicional de Docker (usuario no root), pruebas E2E de frontend, documentación OpenAPI/Swagger, ADRs, y plantillas de GitHub (PR/Issues/CONTRIBUTING/SECURITY).

------------------------------------------------------------------------

# 👤 Autor

-   **Miguel Villalba**
-   📧 mike.mavc27@gmail.com

------------------------------------------------------------------------

# 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo
[LICENSE](LICENSE) para más detalles.