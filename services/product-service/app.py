import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate

from config import build_config
from models import Category, Product, db

SEED_CATEGORIES = ["Electrónica", "Ropa", "Hogar", "Libros"]
SEED_PRODUCTS = [
    dict(name="Auriculares Bluetooth", description="Sonido inalámbrico con cancelación de ruido.",
         price=29.99, stock=50, image_url="https://picsum.photos/seed/audifonos/400", category="Electrónica"),
    dict(name="Smartwatch Fit", description="Monitor de actividad física y notificaciones.",
         price=49.90, stock=30, image_url="https://picsum.photos/seed/smartwatch/400", category="Electrónica"),
    dict(name="Camiseta Básica", description="100% algodón, disponible en varios colores.",
         price=12.50, stock=100, image_url="https://picsum.photos/seed/camiseta/400", category="Ropa"),
    dict(name="Chaqueta Impermeable", description="Ideal para días de lluvia.",
         price=59.99, stock=20, image_url="https://picsum.photos/seed/chaqueta/400", category="Ropa"),
    dict(name="Lámpara de Escritorio", description="Luz LED regulable con puerto USB.",
         price=18.75, stock=40, image_url="https://picsum.photos/seed/lampara/400", category="Hogar"),
    dict(name="Set de Ollas", description="Juego de 5 piezas antiadherentes.",
         price=79.00, stock=15, image_url="https://picsum.photos/seed/ollas/400", category="Hogar"),
    dict(name="Novela de Ciencia Ficción", description="Bestseller internacional, tapa blanda.",
         price=15.20, stock=60, image_url="https://picsum.photos/seed/libro1/400", category="Libros"),
    dict(name="Guía de Programación Python", description="Aprende Python desde cero.",
         price=22.00, stock=35, image_url="https://picsum.photos/seed/libro2/400", category="Libros"),
]


def seed_if_empty():
    if Product.query.first():
        return
    categories = {}
    for name in SEED_CATEGORIES:
        cat = Category(name=name)
        db.session.add(cat)
        categories[name] = cat
    db.session.flush()

    for item in SEED_PRODUCTS:
        product = Product(
            name=item["name"],
            description=item["description"],
            price=item["price"],
            stock=item["stock"],
            image_url=item["image_url"],
            category=categories[item["category"]],
        )
        db.session.add(product)
    db.session.commit()


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    config = build_config(testing=testing)
    app.config.update(config)

    db.init_app(app)
    Migrate(app, db)
    CORS(app, origins=config["CORS_ORIGINS"])

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],
        enabled=not testing,
    )
    app.extensions["ecommerce_limiter"] = limiter

    if testing:
        # En producción el esquema lo crean las migraciones (ver migrations/)
        # y el seed se dispara aparte con `flask seed` (ver entrypoint.sh),
        # porque en este punto (construcción del app) las tablas todavía no
        # existen si migrate no corrió antes.
        with app.app_context():
            db.create_all()

    @app.cli.command("seed")
    def seed_command():
        """Siembra el catálogo de ejemplo si la tabla de productos está vacía."""
        seed_if_empty()
        print("Seed OK")

    register_routes(app, limiter)
    return app


def register_routes(app: Flask, limiter: Limiter) -> None:
    def require_admin() -> bool:
        return request.headers.get("X-Admin-Key") == app.config["ADMIN_API_KEY"]

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="product-service")

    @app.get("/products")
    def list_products():
        query = Product.query
        category = request.args.get("category")
        search = request.args.get("search")
        if category:
            query = query.join(Category).filter(Category.name.ilike(category))
        if search:
            query = query.filter(Product.name.ilike(f"%{search}%"))
        products = query.order_by(Product.id).all()
        return jsonify(products=[p.to_dict() for p in products])

    @app.get("/products/<int:product_id>")
    def get_product(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify(error="producto no encontrado"), 404
        return jsonify(product=product.to_dict())

    @app.get("/categories")
    def list_categories():
        categories = Category.query.order_by(Category.name).all()
        return jsonify(categories=[c.to_dict() for c in categories])

    @app.post("/products")
    @limiter.limit("20 per minute")
    def create_product():
        if not require_admin():
            return jsonify(error="no autorizado"), 403
        data = request.get_json(silent=True) or {}
        required = ("name", "price")
        if not all(data.get(f) not in (None, "") for f in required):
            return jsonify(error="name y price son requeridos"), 400
        try:
            price = float(data["price"])
            stock = int(data.get("stock", 0))
        except (TypeError, ValueError):
            return jsonify(error="price y stock deben ser numéricos"), 400
        if price < 0 or stock < 0:
            return jsonify(error="price y stock no pueden ser negativos"), 400

        category = None
        if data.get("category_id"):
            category = db.session.get(Category, data["category_id"])

        product = Product(
            name=data["name"],
            description=data.get("description", ""),
            price=price,
            stock=stock,
            image_url=data.get("image_url", ""),
            category=category,
        )
        db.session.add(product)
        db.session.commit()
        return jsonify(product=product.to_dict()), 201

    @app.put("/products/<int:product_id>")
    @limiter.limit("20 per minute")
    def update_product(product_id):
        if not require_admin():
            return jsonify(error="no autorizado"), 403
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify(error="producto no encontrado"), 404

        data = request.get_json(silent=True) or {}
        if "price" in data or "stock" in data:
            try:
                if "price" in data:
                    data["price"] = float(data["price"])
                if "stock" in data:
                    data["stock"] = int(data["stock"])
            except (TypeError, ValueError):
                return jsonify(error="price y stock deben ser numéricos"), 400
            if data.get("price", 0) < 0 or data.get("stock", 0) < 0:
                return jsonify(error="price y stock no pueden ser negativos"), 400

        for field in ("name", "description", "price", "stock", "image_url"):
            if field in data:
                setattr(product, field, data[field])
        if "category_id" in data:
            product.category_id = data["category_id"]

        db.session.commit()
        return jsonify(product=product.to_dict())

    @app.delete("/products/<int:product_id>")
    @limiter.limit("20 per minute")
    def delete_product(product_id):
        if not require_admin():
            return jsonify(error="no autorizado"), 403
        product = db.session.get(Product, product_id)
        if not product:
            return jsonify(error="producto no encontrado"), 404
        db.session.delete(product)
        db.session.commit()
        return jsonify(message="producto eliminado")

    @app.post("/internal/reserve-stock")
    def reserve_stock():
        """Usado por order-service para validar y descontar stock al crear un pedido."""
        items = request.get_json(silent=True) or []
        if not isinstance(items, list) or not items:
            return jsonify(error="se requiere una lista de items"), 400

        products_by_id = {}
        for item in items:
            product = db.session.get(Product, item.get("product_id"))
            if not product:
                return jsonify(error=f"producto {item.get('product_id')} no existe"), 404
            quantity = int(item.get("quantity", 0))
            if quantity <= 0:
                return jsonify(error="quantity debe ser mayor a 0"), 400
            if product.stock < quantity:
                return jsonify(error=f"stock insuficiente para '{product.name}'"), 409
            products_by_id[product.id] = (product, quantity)

        reserved = []
        for product, quantity in products_by_id.values():
            product.stock -= quantity
            reserved.append({
                "product_id": product.id,
                "name": product.name,
                "unit_price": float(product.price),
                "quantity": quantity,
            })
        db.session.commit()

        return jsonify(items=reserved)


app = create_app() if os.environ.get("TESTING") != "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
