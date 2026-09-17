import logging
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required
from flask_migrate import Migrate
from sqlalchemy.exc import IntegrityError

from config import build_config
from models import Order, OrderItem, db

PRODUCT_SERVICE_TIMEOUT_SECONDS = 10

logger = logging.getLogger("order-service")


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

    def _release_stock(items: list) -> None:
        """Compensación: intenta devolver stock ya reservado. Best-effort:
        si product-service tampoco responde acá, solo se loguea — queda
        inventario "perdido" hasta una reconciliación manual, documentado
        como limitación conocida (ver README)."""
        payload = [
            {"product_id": i["product_id"], "quantity": i["quantity"]} for i in items
        ]
        try:
            resp = requests.post(
                f"{app.config['PRODUCT_SERVICE_URL']}/internal/release-stock",
                json=payload,
                timeout=PRODUCT_SERVICE_TIMEOUT_SECONDS,
            )
            if resp.status_code != 200:
                logger.error("Falló la compensación de stock: %s", resp.text)
        except requests.RequestException:
            logger.exception("product-service no disponible al compensar stock: %s", payload)

    @app.post("/orders")
    @jwt_required()
    def create_order():
        user_id = int(get_jwt_identity())
        data = request.get_json(silent=True) or {}
        items = data.get("items") or []
        shipping_address = (data.get("shipping_address") or "").strip()
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()

        if not idempotency_key:
            return jsonify(error="el header Idempotency-Key es requerido"), 400
        if not isinstance(items, list) or not items:
            return jsonify(error="el pedido debe tener al menos un item"), 400
        if not shipping_address:
            return jsonify(error="shipping_address es requerido"), 400

        # Idempotencia: si ya procesamos este intento (mismo usuario + key),
        # devolvemos el pedido existente en vez de reservar stock de nuevo.
        existing = Order.query.filter_by(user_id=user_id, idempotency_key=idempotency_key).first()
        if existing:
            return jsonify(order=existing.to_dict()), 200

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

        order = Order(
            user_id=user_id,
            idempotency_key=idempotency_key,
            total=total,
            shipping_address=shipping_address,
            status="paid",
        )
        for item in reserved_items:
            order.items.append(
                OrderItem(
                    product_id=item["product_id"],
                    product_name=item["name"],
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                )
            )

        try:
            db.session.add(order)
            db.session.commit()
        except IntegrityError:
            # Carrera: dos requests con la misma key llegaron casi juntas y
            # ambas pasaron el chequeo de arriba. El stock ya se reservó dos
            # veces; se libera esta reserva duplicada y se devuelve el pedido
            # que sí quedó guardado.
            db.session.rollback()
            _release_stock(reserved_items)
            existing = Order.query.filter_by(user_id=user_id, idempotency_key=idempotency_key).first()
            if existing:
                return jsonify(order=existing.to_dict()), 200
            return jsonify(error="conflicto al guardar el pedido, reintentá"), 409
        except Exception:
            # Cualquier falla acá (DB caída, timeout, bug) deja stock
            # reservado sin pedido asociado si no compensamos: por eso el
            # except es deliberadamente amplio, no solo errores de SQLAlchemy.
            db.session.rollback()
            logger.exception("Falló al guardar el pedido tras reservar stock, compensando...")
            _release_stock(reserved_items)
            return jsonify(error="no se pudo guardar el pedido, el stock reservado fue liberado"), 500

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
