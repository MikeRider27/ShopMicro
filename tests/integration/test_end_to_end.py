"""Prueba de integración real: auth -> order -> product -> reserva de stock.

A diferencia de los tests unitarios de cada servicio (que usan SQLite en
memoria y mockean las llamadas HTTP entre servicios), esta prueba golpea el
stack completo ya desplegado con docker-compose, a través del gateway. No
corre en el pipeline de CI por defecto (requiere `docker compose up`); se usa
para validar manualmente un despliegue local o de staging.

Uso:
    docker compose up -d
    pip install requests pytest
    GATEWAY_URL=http://localhost:8080 pytest tests/integration -v
"""

import os
import uuid

import pytest
import requests

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080")
TIMEOUT = 5


def _gateway_reachable() -> bool:
    try:
        requests.get(f"{GATEWAY_URL}/api/products/health", timeout=TIMEOUT)
        return True
    except requests.RequestException:
        return False


pytestmark = pytest.mark.skipif(
    not _gateway_reachable(),
    reason=f"El gateway no responde en {GATEWAY_URL}; levantá el stack con `docker compose up -d`.",
)


@pytest.fixture(scope="module")
def new_user():
    return {
        "email": f"integration-{uuid.uuid4().hex[:8]}@example.com",
        "password": "integration123",
        "name": "Integration Test",
    }


def test_full_purchase_flow(new_user):
    # 1. Registro (auth-service)
    resp = requests.post(f"{GATEWAY_URL}/api/auth/register", json=new_user, timeout=TIMEOUT)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]

    # 2. Catálogo (product-service)
    resp = requests.get(f"{GATEWAY_URL}/api/products/products", timeout=TIMEOUT)
    assert resp.status_code == 200
    products = resp.json()["products"]
    assert len(products) > 0, "el catálogo debe tener productos sembrados"
    product = next(p for p in products if p["stock"] > 0)
    stock_before = product["stock"]

    # 3. Crear pedido (order-service -> reserva de stock en product-service)
    idempotency_key = uuid.uuid4().hex
    resp = requests.post(
        f"{GATEWAY_URL}/api/orders/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "shipping_address": "Dirección de prueba de integración",
        },
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 201, resp.text
    order = resp.json()["order"]
    assert order["items"][0]["product_id"] == product["id"]

    # 4. El stock debe haberse descontado en product-service
    resp = requests.get(f"{GATEWAY_URL}/api/products/products/{product['id']}", timeout=TIMEOUT)
    assert resp.json()["product"]["stock"] == stock_before - 1

    # 5. El pedido debe aparecer en el historial del usuario
    resp = requests.get(
        f"{GATEWAY_URL}/api/orders/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    order_ids = [o["id"] for o in resp.json()["orders"]]
    assert order["id"] in order_ids

    # 6. Reenviar la misma request con la misma key no debe crear un segundo
    #    pedido ni descontar stock de nuevo (idempotencia).
    resp = requests.post(
        f"{GATEWAY_URL}/api/orders/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 1}],
            "shipping_address": "Dirección de prueba de integración",
        },
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": idempotency_key},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["order"]["id"] == order["id"]

    resp = requests.get(f"{GATEWAY_URL}/api/products/products/{product['id']}", timeout=TIMEOUT)
    assert resp.json()["product"]["stock"] == stock_before - 1


def test_order_rejected_without_auth():
    resp = requests.post(
        f"{GATEWAY_URL}/api/orders/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "x"},
        headers={"Idempotency-Key": uuid.uuid4().hex},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 401


def _login(user):
    resp = requests.post(
        f"{GATEWAY_URL}/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
        timeout=TIMEOUT,
    )
    return resp.json()["access_token"]


def test_order_rejected_without_idempotency_key(new_user):
    token = _login(new_user)

    resp = requests.post(
        f"{GATEWAY_URL}/api/orders/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "x"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 400


def test_order_rejected_when_stock_insufficient(new_user):
    token = _login(new_user)

    resp = requests.get(f"{GATEWAY_URL}/api/products/products", timeout=TIMEOUT)
    product = resp.json()["products"][0]

    resp = requests.post(
        f"{GATEWAY_URL}/api/orders/orders",
        json={
            "items": [{"product_id": product["id"], "quantity": 999999}],
            "shipping_address": "x",
        },
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": uuid.uuid4().hex},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 409
