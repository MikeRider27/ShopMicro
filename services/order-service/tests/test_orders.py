from unittest.mock import patch

import requests


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_create_order_requires_auth(client):
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "x"},
    )
    assert resp.status_code == 401


def test_create_order_missing_items(client, auth_headers):
    resp = client.post(
        "/orders", json={"items": [], "shipping_address": "Calle 1"}, headers=auth_headers
    )
    assert resp.status_code == 400


def test_create_order_missing_address(client, auth_headers):
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_create_order_invalid_item_shape(client, auth_headers):
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": "abc", "quantity": 1}], "shipping_address": "Calle 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@patch("app.requests.post")
def test_create_order_success(mock_post, client, auth_headers):
    mock_post.return_value = FakeResponse(
        200,
        {"items": [{"product_id": 1, "name": "Producto", "unit_price": 10.0, "quantity": 2}]},
    )
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 2}], "shipping_address": "Calle 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    order = resp.get_json()["order"]
    assert order["total"] == 20.0
    assert order["items"][0]["product_name"] == "Producto"


@patch("app.requests.post")
def test_create_order_insufficient_stock(mock_post, client, auth_headers):
    mock_post.return_value = FakeResponse(409, {"error": "stock insuficiente"})
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 999}], "shipping_address": "Calle 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@patch("app.requests.post")
def test_create_order_product_service_unavailable(mock_post, client, auth_headers):
    mock_post.side_effect = requests.RequestException("connection refused")
    resp = client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "Calle 1"},
        headers=auth_headers,
    )
    assert resp.status_code == 503


def test_list_orders_empty(client, auth_headers):
    resp = client.get("/orders", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["orders"] == []


@patch("app.requests.post")
def test_list_orders_after_creation(mock_post, client, auth_headers):
    mock_post.return_value = FakeResponse(
        200,
        {"items": [{"product_id": 1, "name": "Producto", "unit_price": 5.0, "quantity": 1}]},
    )
    client.post(
        "/orders",
        json={"items": [{"product_id": 1, "quantity": 1}], "shipping_address": "Calle 1"},
        headers=auth_headers,
    )
    resp = client.get("/orders", headers=auth_headers)
    assert len(resp.get_json()["orders"]) == 1


def test_get_order_not_found(client, auth_headers):
    resp = client.get("/orders/999", headers=auth_headers)
    assert resp.status_code == 404
