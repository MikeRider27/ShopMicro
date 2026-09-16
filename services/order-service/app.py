import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, jwt_required

from config import Config
from models import Order, OrderItem, db

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
jwt = JWTManager(app)
CORS(app)

with app.app_context():
    db.create_all()


@app.get("/health")
def health():
    return jsonify(status="ok", service="order-service")


@app.post("/orders")
@jwt_required()
def create_order():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    shipping_address = data.get("shipping_address", "")

    if not items:
        return jsonify(error="el pedido debe tener al menos un item"), 400

    reserve_payload = [
        {"product_id": item.get("product_id"), "quantity": item.get("quantity")}
        for item in items
    ]

    try:
        resp = requests.post(
            f"{app.config['PRODUCT_SERVICE_URL']}/internal/reserve-stock",
            json=reserve_payload,
            timeout=10,
        )
    except requests.RequestException:
        return jsonify(error="product-service no disponible"), 503

    if resp.status_code != 200:
        return jsonify(error=resp.json().get("error", "no se pudo reservar el stock")), resp.status_code

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
