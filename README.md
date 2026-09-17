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
| todos | GET | `/api/<auth\|products\|orders>/health` | Liveness (no depende de nada externo) |
| todos | GET | `/api/<auth\|products\|orders>/readiness` | Readiness (chequea Postgres y, si aplica, Redis) |
| todos | GET | `/api/<auth\|products\|orders>/metrics` | Métricas en formato Prometheus |

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

## Validación de requests

Los tres microservicios validan el body de sus endpoints de escritura con [Marshmallow](https://marshmallow.readthedocs.io/) (`schemas.py` en cada servicio) en vez de `if`s sueltos:

- **Tipos y rangos:** `email` con formato válido (auth-service), `price`/`stock` numéricos y no negativos, `quantity`/`product_id` enteros positivos (product-service, order-service).
- **Campos arbitrarios rechazados:** marshmallow usa `unknown="raise"` por default — mandar un campo no declarado (ej. `is_admin` en un registro, o `total` en la creación de un pedido) devuelve `400` en vez de ignorarse silenciosamente.
- **Antes de tocar la base o a otro servicio:** la validación corre primero; recién si pasa se consulta la base de datos o se llama a `product-service`.
## Manejo de errores

Los tres microservicios devuelven todos sus errores con el mismo formato:

```json
{ "error": { "code": "PRODUCT_NOT_FOUND", "message": "producto no encontrado" } }
```

`details` aparece solo cuando aplica (errores de validación, con el detalle por campo de marshmallow). Esto lo resuelven handlers globales (`errors.py` en cada servicio), no cada endpoint por separado:

- Errores de validación (`marshmallow.ValidationError`) → `400 VALIDATION_ERROR` con `details`.
- Cualquier `HTTPException` de Flask/Werkzeug (404 de una ruta que no existe, 405, 429 del rate limiter, etc.) → mismo formato, con un code genérico según el status (`NOT_FOUND`, `METHOD_NOT_ALLOWED`, `RATE_LIMITED`...).
- Fallas de JWT (auth-service, order-service) → `MISSING_TOKEN` / `TOKEN_EXPIRED` (401) o `INVALID_TOKEN` (422), en vez del `{"msg": "..."}` que da flask-jwt-extended por default.
- Cualquier excepción no prevista → `500 INTERNAL_ERROR` genérico; el detalle real (traceback, mensaje de SQL, etc.) se loguea del lado del servidor pero **nunca** se manda al cliente.
- Errores de negocio tienen su propio code (`EMAIL_ALREADY_REGISTERED`, `INSUFFICIENT_STOCK`, `INVALID_ADMIN_KEY`, `ORDER_NOT_FOUND`, etc.), así el frontend (o cualquier consumidor de la API) puede reaccionar a un `code` en vez de parsear el texto del `message`.
- Cuando `order-service` reenvía un error de `product-service` (ej. al reservar stock), propaga el `code`/`message` originales en vez de taparlos con un mensaje genérico (ver `parse_upstream_error` en `services/order-service/errors.py`).

## Comunicación entre microservicios

- **Timeouts explícitos:** toda llamada de `order-service` a `product-service` tiene un timeout de 10s (`PRODUCT_SERVICE_TIMEOUT_SECONDS`) — nunca se queda esperando indefinidamente si el otro servicio no responde.
- **Reintentos, pero solo donde son seguros:** `reserve-stock` y `release-stock` **no son idempotentes** (llamarlos dos veces descuenta/devuelve stock dos veces), así que `order-service` reintenta (hasta 2 veces, con backoff corto) *solo* ante `ConnectionError` — el request nunca llegó al otro servicio, reintentar no tiene riesgo. Un timeout de lectura (`ReadTimeout`, el request sí pudo haber llegado y procesarse) **no se reintenta**: se propaga como `503` de inmediato, para no arriesgar una doble reserva. Ver `_post_to_product_service` en `services/order-service/app.py`.
- **Correlation ID (`X-Request-ID`):** el frontend genera un UUID por request (`frontend/lib/api.ts`); el gateway lo respeta si viene, o genera uno con `$request_id` de nginx si no; cada microservicio lo lee (o genera uno si lo llaman directo), lo devuelve en la respuesta, y lo incluye en cada línea de log (`middleware.py` en cada servicio) — incluida la propagación de `order-service` hacia `product-service` en las llamadas internas. Esto permite seguir un mismo request a través de los logs de varios servicios (ver ejemplo en la sección de Observabilidad).
- **URLs de servicios centralizadas:** `docker-compose.yml` es la única fuente de verdad de cómo se direccionan los servicios entre sí (`PRODUCT_SERVICE_URL=http://product-service:5002`, nombres de servicio = hostnames de Docker); `config.py` de cada servicio solo tiene un fallback para correrlo suelto (tests, `flask run` local).

## Observabilidad

- **Logs estructurados (JSON):** cada línea de log de los 3 servicios es un objeto JSON (`timestamp`, `level`, `logger`, `message`, `request_id`, y cualquier campo extra), listo para mandar a ELK/Loki/CloudWatch sin parsear texto plano (`JsonFormatter` en `middleware.py`). Ejemplo real, un pedido creado — notá el mismo `request_id` en ambos servicios:
  ```json
  {"timestamp": "2026-09-17T20:20:22+0000", "logger": "product-service", "message": "stock_reserved", "request_id": "ecac48b7...", "event": "stock_reserved", "items": [{"product_id": 1, "quantity": 1}]}
  {"timestamp": "2026-09-17T20:20:22+0000", "logger": "order-service", "message": "order_created", "request_id": "ecac48b7...", "event": "order_created", "order_id": 1, "user_id": 1, "total": 29.99, "item_count": 1}
  ```
- **Nunca se loguean credenciales:** ni contraseñas, ni tokens JWT, ni `X-Admin-Key`, ni el body de los requests. Los eventos de negocio (`log_event`) solo llevan IDs, cantidades y montos — por ejemplo `user_registered` loguea `user_id`, nunca el email.
- **Eventos de negocio registrados:** `user_registered` (auth-service), `stock_reserved` / `stock_released` (product-service), `order_created` / `order_idempotent_replay` / `order_stock_compensated` (order-service).
- **Métricas básicas:** cada servicio expone `GET /metrics` en formato Prometheus — `http_requests_total`, `http_request_duration_seconds` y `http_request_errors_total`, con labels de método/endpoint/status. No requiere infraestructura extra, cualquier Prometheus puede scrapearlo directo.
- **Health vs. readiness:** `GET /health` (liveness) no depende de nada externo — si responde, el proceso está vivo. `GET /readiness` chequea Postgres (y Redis donde aplica) y devuelve `503` si alguno falla; es lo que usa el `healthcheck` de `docker-compose.yml` para no marcar un servicio como sano si todavía no puede atender tráfico de verdad.

## Notas de diseño / simplificaciones

- Cada microservicio usa su propia base de datos dentro del mismo Postgres (aislamiento lógico, sin compartir tablas).
- La escritura del catálogo (`POST/PUT/DELETE /products`) está protegida por un header simple `X-Admin-Key` (variable `ADMIN_API_KEY`), pensado para administración interna, no para el frontend público.
- El carrito de compras vive en el cliente (localStorage), no hay carrito persistido en base de datos.

## Roadmap

Mejoras identificadas y no incluidas todavía en este alcance: hardening adicional de Docker (usuario no root, versiones de imágenes base fijadas), pruebas E2E de frontend, documentación OpenAPI/Swagger, ADRs, y plantillas de GitHub (PR/Issues/CONTRIBUTING/SECURITY). También quedan pendientes, mencionados por el plan de mejoras pero fuera de este alcance: un Prometheus/Grafana real scrapeando los `/metrics` (hoy solo se exponen), y agregación centralizada de logs (hoy quedan en `docker compose logs`, no en un ELK/Loki).

------------------------------------------------------------------------

# 👤 Autor

-   **Miguel Villalba**
-   📧 mike.mavc27@gmail.com

------------------------------------------------------------------------

# 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo
[LICENSE](LICENSE) para más detalles.