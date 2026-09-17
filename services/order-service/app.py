import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required
from flask_migrate import Migrate

from config import build_config
from models import Order, OrderItem, db

PRODUCT_SERVICE_TIMEOUT_SECONDS = 10


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    config = build_config(testing=testing)
    app.config.update(config)

    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)
    CORS(app, origins=config["CORS_ORIGINS"])

    if testing:
        # En producción el esquema lo crean las migraciones (ver migrations/).
        with app.app_context():
            db.create_all()

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.get("/health")
    def health():
        return jsonify(status="ok", service="order-service")

    @app.post("/orders")
    @jwt_required()
    def create_order():
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        items = data.get("items") or []
        shipping_address = (data.get("shipping_address") or "").strip()

        if not isinstance(items, list) or not items:
            return jsonify(error="el pedido debe tener al menos un item"), 400
        if not shipping_address:
            return jsonify(error="shipping_address es requerido"), 400

        reserve_payload = []
        for item in items:
            product_id = item.get("product_id")
            quantity = item.get("quantity")
            if not isinstance(product_id, int) or not isinstance(quantity, int) or quantity <= 0:
                return jsonify(error="cada item requiere product_id y quantity (entero positivo)"), 400
            reserve_payload.append({"product_id": product_id, "quantity": quantity})

        try:
            resp = requests.post(
                f"{app.config['PRODUCT_SERVICE_URL']}/internal/reserve-stock",
                json=reserve_payload,
                timeout=PRODUCT_SERVICE_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            return jsonify(error="product-service no disponible"), 503

        if resp.status_code != 200:
            error_message = resp.json().get("error", "no se pudo reservar el stock")
            return jsonify(error=error_message), resp.status_code

        reserved_items = resp.json()["items"]
        total = sum(i["unit_price"] * i["quantity"] for i in reserved_items)

        order = Order(user_id=user_id, total=total, shipping_address=shipping_address, status="paid")
        for item in reserved_items:
            order.items.append(
                OrderItem(
                    product_id=item["product_id"],
                    product_name=item["name"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                )
            )
        db.session.add(order)
        db.session.commit()

        return jsonify(order=order.to_dict()), 201

    @app.get("/orders")
    @jwt_required()
    def list_my_orders():
        user_id = int(get_jwt_identity())
        orders = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).all()
        return jsonify(orders=[o.to_dict() for o in orders])

    @app.get("/orders/<int:order_id>")
    @jwt_required()
    def get_order(order_id):
        user_id = int(get_jwt_identity())
        order = db.session.get(Order, order_id)
        if not order or order.user_id != user_id:
            return jsonify(error="pedido no encontrado"), 404
        return jsonify(order=order.to_dict())


app = create_app() if os.environ.get("TESTING") != "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
