import os

os.environ["TESTING"] = "1"

import pytest

from app import create_app
from models import db

ADMIN_HEADERS = {"X-Admin-Key": "test-admin-key"}


@pytest.fixture
def app():
    flask_app = create_app(testing=True)
    yield flask_app
    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_product(client):
    resp = client.post(
        "/products",
        json={"name": "Producto de prueba", "price": 10.0, "stock": 5},
        headers=ADMIN_HEADERS,
    )
    return resp.get_json()["product"]
