import os

os.environ["TESTING"] = "1"

import pytest

from app import create_app
from models import db


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
