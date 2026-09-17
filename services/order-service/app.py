import logging
import os
import time

import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required
from flask_migrate import Migrate
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from config import build_config
from errors import error_response, parse_upstream_error, register_error_handlers
from middleware import log_event, register_request_id
from metrics import register_metrics
from models import Order, OrderItem, db
from schemas import CreateOrderSchema

PRODUCT_SERVICE_TIMEOUT_SECONDS = 10

# reserve-stock y release-stock NO son idempotentes (llamarlos dos veces
# descuenta/devuelve stock dos veces), así que solo es seguro reintentarlos
# cuando el request nunca llegó a product-service (ConnectionError). Un
# Timeout NO se reintenta acá: no sabemos si ya se procesó del otro lado.
MAX_CONNECTION_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.2

logger = logging.getLogger("order-service")


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    config = build_config(testing=testing)
    app.config.update(config)

    db.init_app(app)
    Migrate(app, db)
    jwt = JWTManager(app)
    CORS(app, origins=config["CORS_ORIGINS"])
    register_error_handlers(app)
    register_jwt_error_handlers(jwt)
    register_request_id(app, "order-service")
    register_metrics(app)

    if testing:
        # En producción el esquema lo crean las migraciones (ver migrations/).
        with app.app_context():
            db.create_all()

    register_routes(app)
    return app


def register_jwt_error_handlers(jwt: JWTManager) -> None:
    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response("MISSING_TOKEN", "se requiere un token de autenticación", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response("INVALID_TOKEN", "token inválido", 422)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("TOKEN_EXPIRED", "el token expiró, iniciá sesión de nuevo", 401)


def register_routes(app: Flask) -> None:
    def _post_to_product_service(path: str, json_payload):
        """POST a product-service, propagando el X-Request-ID del request
        actual para poder correlacionar logs entre los dos servicios.

        Reintenta (hasta MAX_CONNECTION_RETRIES veces) solo si la conexión
        falló antes de llegar a destino (ConnectionError/ConnectTimeout). Un
        Timeout de lectura (el request sí llegó, product-service tardó en
        responder) se propaga sin reintentar: reserve-stock/release-stock no
        son idempotentes, reintentar ahí podría descontar o devolver stock
        dos veces.
        """
        url = f"{app.config['PRODUCT_SERVICE_URL']}{path}"
        headers = {"X-Request-ID": g.get("request_id", "-")}
        attempt = 0
        while True:
            try:
                return requests.post(
                    url, json=json_payload, timeout=PRODUCT_SERVICE_TIMEOUT_SECONDS, headers=headers
                )
            except requests.exceptions.ConnectionError:
                attempt += 1
                if attempt > MAX_CONNECTION_RETRIES:
                    raise
                logger.warning(
                    "No se pudo conectar a product-service (intento %s/%s), reintentando...",
                    attempt,
                    MAX_CONNECTION_RETRIES,
                )
                time.sleep(RETRY_BACKOFF_SECONDS)

    @app.get("/health")
    def health():
        """Liveness: el proceso está vivo. No depende de nada externo."""
        return jsonify(status="ok", service="order-service")

    @app.get("/readiness")
    def readiness():
        """Readiness: Postgres responde. No chequea product-service a
        propósito — si product-service tiene un problema puntual, order-service
        igual puede atender GET /orders normalmente; marcarlo "no ready" acá
        provocaría una falla en cascada innecesaria."""
        checks = {}
        try:
            db.session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "error"

        if all(v == "ok" for v in checks.values()):
            return jsonify(status="ready", checks=checks)
        return error_response("NOT_READY", "el servicio no está listo", 503, details=checks)

    def _release_stock(items: list) -> None:
        """Compensación: intenta devolver stock ya reservado. Best-effort:
        si product-service tampoco responde acá, solo se loguea — queda
        inventario "perdido" hasta una reconciliación manual, documentado
        como limitación conocida (ver README)."""
        payload = [
            {"product_id": i["product_id"], "quantity": i["quantity"]} for i in items
        ]
        try:
            resp = _post_to_product_service("/internal/release-stock", payload)
            if resp.status_code != 200:
                logger.error("Falló la compensación de stock: %s", resp.text)
        except requests.RequestException:
            logger.exception("product-service no disponible al compensar stock: %s", payload)

    @app.post("/orders")
    @jwt_required()
    def create_order():
        user_id = int(get_jwt_identity())
        idempotency_key = request.headers.get("Idempotency-Key", "").strip()
        if not idempotency_key:
            return error_response("MISSING_IDEMPOTENCY_KEY", "el header Idempotency-Key es requerido", 400)

        payload = CreateOrderSchema().load(request.get_json(silent=True) or {})
        shipping_address = payload["shipping_address"]

        # Idempotencia: si ya procesamos este intento (mismo usuario + key),
        # devolvemos el pedido existente en vez de reservar stock de nuevo.
        existing = Order.query.filter_by(user_id=user_id, idempotency_key=idempotency_key).first()
        if existing:
            log_event("order-service", "order_idempotent_replay", order_id=existing.id, user_id=user_id)
            return jsonify(order=existing.to_dict()), 200

        reserve_payload = [
            {"product_id": item["product_id"], "quantity": item["quantity"]}
            for item in payload["items"]
        ]

        try:
            resp = _post_to_product_service("/internal/reserve-stock", reserve_payload)
        except requests.RequestException:
            return error_response("PRODUCT_SERVICE_UNAVAILABLE", "product-service no disponible", 503)

        if resp.status_code != 200:
            code, message = parse_upstream_error(resp, "STOCK_RESERVATION_FAILED", "no se pudo reservar el stock")
            return error_response(code, message, resp.status_code)

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
            log_event("order-service", "order_stock_compensated", reason="idempotency_race", items=reserved_items)
            _release_stock(reserved_items)
            existing = Order.query.filter_by(user_id=user_id, idempotency_key=idempotency_key).first()
            if existing:
                return jsonify(order=existing.to_dict()), 200
            return error_response("ORDER_CONFLICT", "conflicto al guardar el pedido, reintentá", 409)
        except Exception:
            # Cualquier falla acá (DB caída, timeout, bug) deja stock
            # reservado sin pedido asociado si no compensamos: por eso el
            # except es deliberadamente amplio, no solo errores de SQLAlchemy.
            db.session.rollback()
            logger.exception("Falló al guardar el pedido tras reservar stock, compensando...")
            log_event("order-service", "order_stock_compensated", reason="save_failed", items=reserved_items)
            _release_stock(reserved_items)
            return error_response(
                "ORDER_SAVE_FAILED",
                "no se pudo guardar el pedido, el stock reservado fue liberado",
                500,
            )

        log_event(
            "order-service",
            "order_created",
            order_id=order.id,
            user_id=user_id,
            total=float(order.total),
            item_count=len(order.items),
        )
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
            return error_response("ORDER_NOT_FOUND", "pedido no encontrado", 404)
        return jsonify(order=order.to_dict())


app = create_app() if os.environ.get("TESTING") != "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
