# ShopMicro — E-commerce con Next.js + microservicios Flask

Arquitectura:

```
frontend (Next.js, :3000)
   │
   ▼
gateway (Nginx, :8080)  ──/api/auth/──▶ auth-service (Flask, :5001)
                          ──/api/products/──▶ product-service (Flask, :5002)
                          ──/api/orders/──▶ order-service (Flask, :5003) ──▶ product-service (reserva de stock)

Postgres externo: 192.168.11.220:5436 (una base de datos por microservicio)
```

- **auth-service**: registro/login de usuarios, emite JWT (`ecommerce_auth`).
- **product-service**: catálogo de productos y categorías, con seed de datos de ejemplo (`ecommerce_products`).
- **order-service**: crea pedidos validando y descontando stock vía `product-service`, protegido con JWT (`ecommerce_orders`).
- **gateway**: Nginx enruta `/api/*` a cada microservicio.
- **frontend**: catálogo, carrito (persistido en localStorage), login/registro, checkout e historial de pedidos.

## 1. Preparar la base de datos (una sola vez)

El Postgres es externo y compartido, así que hay que crear las 3 bases de datos antes de levantar los servicios:

```bash
PGPASSWORD=123 psql -h 192.168.11.220 -p 5436 -U postgres -f init-db.sql
```

Si no tienes `psql` instalado localmente, puedes ejecutarlo desde un contenedor:

```bash
docker run --rm -e PGPASSWORD=123 -v "$(pwd)/init-db.sql:/init-db.sql" postgres:16-alpine \
  psql -h 192.168.11.220 -p 5436 -U postgres -f /init-db.sql
```

Cada microservicio crea sus propias tablas automáticamente al arrancar (`db.create_all()`), y `product-service` inserta un catálogo de ejemplo si la tabla está vacía.

## 2. Variables de entorno

Copia `.env.example` a `.env` y ajusta si lo necesitas (por defecto ya apunta al Postgres indicado):

```bash
cp .env.example .env
```

## 3. Levantar todo con Docker

```bash
docker compose up --build
```

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

## Notas de diseño / simplificaciones

- Cada microservicio usa su propia base de datos en el mismo Postgres externo (aislamiento lógico, sin compartir tablas).
- `order-service` llama a `product-service` (`/internal/reserve-stock`) para validar y descontar stock de forma síncrona al crear un pedido.
- La escritura del catálogo (`POST/PUT/DELETE /products`) está protegida por un header simple `X-Admin-Key` (variable `ADMIN_API_KEY`), pensado para administración interna, no para el frontend público.
- El carrito de compras vive en el cliente (localStorage), no hay carrito persistido en base de datos.
- Para producción real: sustituir `JWT_SECRET_KEY` y `ADMIN_API_KEY` por secretos fuertes, y considerar HTTPS en el gateway.

------------------------------------------------------------------------

# 👤 Autor

-   **Miguel Villalba**
-   📧 mike.mavc27@gmail.com

------------------------------------------------------------------------

# 📄 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo
[LICENSE](LICENSE) para más detalles.