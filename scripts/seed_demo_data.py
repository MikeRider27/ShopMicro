"""Siembra datos de demo (productos, usuarios y pedidos) llamando a la API pública
a través del gateway. No toca la base de datos directamente: usa los mismos
endpoints que usaría el frontend, así respeta las reglas de cada microservicio
(hash de contraseñas, descuento de stock, etc).

Uso:
    python3 scripts/seed_demo_data.py
    GATEWAY_URL=http://localhost:8091 ADMIN_API_KEY=... python3 scripts/seed_demo_data.py
"""

import json
import os
import random
import urllib.error
import urllib.request

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8091")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "change-me-in-production")

EXTRA_PRODUCTS = [
    dict(name="Teclado Mecánico RGB", description="Switches azules, retroiluminado.",
         price=45.00, stock=25, image_url="https://picsum.photos/seed/teclado/400", category="Electrónica"),
    dict(name="Mouse Inalámbrico", description="Ergonómico, batería de larga duración.",
         price=19.99, stock=60, image_url="https://picsum.photos/seed/mouse/400", category="Electrónica"),
    dict(name="Parlante Portátil", description="Bluetooth, resistente al agua.",
         price=34.50, stock=40, image_url="https://picsum.photos/seed/parlante/400", category="Electrónica"),
    dict(name="Jean Slim Fit", description="Corte moderno, varios talles.",
         price=32.00, stock=45, image_url="https://picsum.photos/seed/jean/400", category="Ropa"),
    dict(name="Zapatillas Running", description="Amortiguación ligera para largas distancias.",
         price=65.00, stock=25, image_url="https://picsum.photos/seed/zapatillas/400", category="Ropa"),
    dict(name="Gorra Deportiva", description="Ajustable, protección UV.",
         price=14.90, stock=70, image_url="https://picsum.photos/seed/gorra/400", category="Ropa"),
    dict(name="Set de Toallas", description="Juego de 4 toallas de algodón egipcio.",
         price=27.00, stock=30, image_url="https://picsum.photos/seed/toallas/400", category="Hogar"),
    dict(name="Difusor de Aromas", description="Con luz LED de 7 colores.",
         price=21.50, stock=35, image_url="https://picsum.photos/seed/difusor/400", category="Hogar"),
    dict(name="Organizador Multiuso", description="Compartimentos apilables para el hogar.",
         price=16.25, stock=50, image_url="https://picsum.photos/seed/organizador/400", category="Hogar"),
    dict(name="Atlas Histórico Ilustrado", description="Mapas y cronologías desde la antigüedad.",
         price=28.00, stock=20, image_url="https://picsum.photos/seed/atlas/400", category="Libros"),
    dict(name="Cuentos Cortos Latinoamericanos", description="Antología de autores contemporáneos.",
         price=13.40, stock=45, image_url="https://picsum.photos/seed/cuentos/400", category="Libros"),
    dict(name="Guía de Diseño UX/UI", description="Principios prácticos con ejemplos reales.",
         price=24.90, stock=30, image_url="https://picsum.photos/seed/uxui/400", category="Libros"),
]

DEMO_USERS = [
    dict(name="Ana Torres", email="ana@example.com", password="demo1234"),
    dict(name="Carlos Ruiz", email="carlos@example.com", password="demo1234"),
    dict(name="María López", email="maria@example.com", password="demo1234"),
]


def call(method, path, body=None, token=None, headers=None):
    url = f"{GATEWAY_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "{}")


def get_categories():
    status, data = call("GET", "/api/products/categories")
    return {c["name"]: c["id"] for c in data.get("categories", [])}


def seed_products():
    categories = get_categories()
    created = 0
    for item in EXTRA_PRODUCTS:
        category_id = categories.get(item["category"])
        payload = {**item, "category_id": category_id}
        payload.pop("category")
        status, data = call(
            "POST", "/api/products/products", body=payload,
            headers={"X-Admin-Key": ADMIN_API_KEY},
        )
        if status == 201:
            created += 1
        else:
            print(f"  ! no se pudo crear '{item['name']}': {data.get('error')}")
    print(f"Productos nuevos creados: {created}/{len(EXTRA_PRODUCTS)}")


def register_or_login(user):
    status, data = call("POST", "/api/auth/register", body=user)
    if status == 201:
        return data["access_token"], data["user"]
    status, data = call(
        "POST", "/api/auth/login",
        body={"email": user["email"], "password": user["password"]},
    )
    if status == 200:
        return data["access_token"], data["user"]
    raise RuntimeError(f"no se pudo registrar/loguear a {user['email']}: {data}")


def seed_users_and_orders():
    status, data = call("GET", "/api/products/products")
    products = data.get("products", [])
    if not products:
        print("  ! no hay productos disponibles para crear pedidos")
        return

    addresses = [
        "Av. Siempre Viva 742, Springfield",
        "Calle Reforma 100, CDMX",
        "Jirón de la Unión 500, Lima",
        "Carrera 7 #45-10, Bogotá",
    ]

    for user in DEMO_USERS:
        token, created_user = register_or_login(user)
        print(f"Usuario listo: {created_user['email']} (id={created_user['id']})")

        num_orders = random.randint(1, 2)
        for _ in range(num_orders):
            chosen = random.sample(products, k=min(2, len(products)))
            items = [
                {"product_id": p["id"], "quantity": random.randint(1, 3)}
                for p in chosen
                if p["stock"] > 0
            ]
            if not items:
                continue
            status, data = call(
                "POST", "/api/orders/orders",
                body={"items": items, "shipping_address": random.choice(addresses)},
                token=token,
            )
            if status == 201:
                print(f"  Pedido #{data['order']['id']} creado (total ${data['order']['total']:.2f})")
            else:
                print(f"  ! no se pudo crear pedido: {data.get('error')}")


if __name__ == "__main__":
    print(f"Sembrando datos de demo contra {GATEWAY_URL} ...")
    print("\n== Productos ==")
    seed_products()
    print("\n== Usuarios y pedidos ==")
    seed_users_and_orders()
    print("\nListo.")
