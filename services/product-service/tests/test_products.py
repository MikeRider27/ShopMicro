from conftest import ADMIN_HEADERS


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_products_empty(client):
    resp = client.get("/products")
    assert resp.status_code == 200
    assert resp.get_json()["products"] == []


def test_create_product_requires_admin_key(client):
    resp = client.post("/products", json={"name": "X", "price": 1})
    assert resp.status_code == 403


def test_create_product_success(client):
    resp = client.post(
        "/products",
        json={"name": "Teclado", "price": 25.5, "stock": 10},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 201
    data = resp.get_json()["product"]
    assert data["name"] == "Teclado"
    assert data["stock"] == 10


def test_create_product_missing_fields(client):
    resp = client.post("/products", json={"price": 5}, headers=ADMIN_HEADERS)
    assert resp.status_code == 400


def test_create_product_negative_price(client):
    resp = client.post(
        "/products", json={"name": "X", "price": -5}, headers=ADMIN_HEADERS
    )
    assert resp.status_code == 400


def test_get_product_not_found(client):
    resp = client.get("/products/999")
    assert resp.status_code == 404


def test_get_product_found(client, sample_product):
    resp = client.get(f"/products/{sample_product['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["product"]["id"] == sample_product["id"]


def test_update_product_requires_admin_key(client, sample_product):
    resp = client.put(f"/products/{sample_product['id']}", json={"stock": 1})
    assert resp.status_code == 403


def test_update_product_success(client, sample_product):
    resp = client.put(
        f"/products/{sample_product['id']}",
        json={"stock": 1},
        headers=ADMIN_HEADERS,
    )
    assert resp.status_code == 200
    assert resp.get_json()["product"]["stock"] == 1


def test_delete_product_success(client, sample_product):
    resp = client.delete(f"/products/{sample_product['id']}", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert client.get(f"/products/{sample_product['id']}").status_code == 404


def test_reserve_stock_success(client, sample_product):
    resp = client.post(
        "/internal/reserve-stock",
        json=[{"product_id": sample_product["id"], "quantity": 2}],
    )
    assert resp.status_code == 200
    items = resp.get_json()["items"]
    assert items[0]["quantity"] == 2

    updated = client.get(f"/products/{sample_product['id']}").get_json()["product"]
    assert updated["stock"] == sample_product["stock"] - 2


def test_reserve_stock_insufficient(client, sample_product):
    resp = client.post(
        "/internal/reserve-stock",
        json=[{"product_id": sample_product["id"], "quantity": 999}],
    )
    assert resp.status_code == 409


def test_reserve_stock_unknown_product(client):
    resp = client.post(
        "/internal/reserve-stock", json=[{"product_id": 999, "quantity": 1}]
    )
    assert resp.status_code == 404


def test_release_stock_restores_quantity(client, sample_product):
    client.post(
        "/internal/reserve-stock",
        json=[{"product_id": sample_product["id"], "quantity": 3}],
    )
    resp = client.post(
        "/internal/release-stock",
        json=[{"product_id": sample_product["id"], "quantity": 3}],
    )
    assert resp.status_code == 200
    assert resp.get_json()["released"] == [
        {"product_id": sample_product["id"], "quantity": 3}
    ]

    updated = client.get(f"/products/{sample_product['id']}").get_json()["product"]
    assert updated["stock"] == sample_product["stock"]


def test_release_stock_skips_unknown_product(client):
    resp = client.post(
        "/internal/release-stock", json=[{"product_id": 999, "quantity": 1}]
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["released"] == []
    assert data["skipped"] == [999]
