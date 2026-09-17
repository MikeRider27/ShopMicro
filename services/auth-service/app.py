import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from marshmallow import ValidationError

from config import build_config
from models import User, db
from schemas import LoginSchema, RegisterSchema


def parse_json(schema):
    """Valida el body JSON contra un schema de marshmallow.

    Devuelve (payload, None) si es válido, o (None, (response, 400)) con el
    detalle de los errores por campo si no lo es. Rechaza tipos incorrectos,
    campos faltantes y campos desconocidos (unknown="raise", el default de
    marshmallow) antes de tocar la base de datos.
    """
    try:
        return schema.load(request.get_json(silent=True) or {}), None
    except ValidationError as err:
        return None, (jsonify(error="datos inválidos", details=err.messages), 400)


def create_app(testing: bool = False) -> Flask:
    app = Flask(__name__)
    config = build_config(testing=testing)
    app.config.update(config)

    db.init_app(app)
    Migrate(app, db)
    JWTManager(app)
    CORS(app, origins=config["CORS_ORIGINS"])

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],
        enabled=not testing,
    )
    # Flask-Limiter guarda una weakref al Limiter; sin esta referencia fuerte
    # el objeto puede ser recolectado y los decoradores @limiter.limit fallan.
    app.extensions["ecommerce_limiter"] = limiter

    if testing:
        # En tests usamos SQLite en memoria: más simple que correr migraciones.
        # En producción el esquema lo crean las migraciones (ver migrations/),
        # no create_all(), para poder versionar y revertir cambios de esquema.
        with app.app_context():
            db.create_all()

    register_routes(app, limiter)
    return app


def register_routes(app: Flask, limiter: Limiter) -> None:
    @app.get("/health")
    def health():
        return jsonify(status="ok", service="auth-service")

    @app.post("/register")
    @limiter.limit("10 per minute")
    def register():
        payload, error = parse_json(RegisterSchema())
        if error:
            return error

        email = payload["email"].strip().lower()
        name = payload["name"].strip()

        if User.query.filter_by(email=email).first():
            return jsonify(error="el email ya está registrado"), 409

        user = User(email=email, name=name)
        user.set_password(payload["password"])
        db.session.add(user)
        db.session.commit()

        token = create_access_token(identity=str(user.id))
        return jsonify(user=user.to_dict(), access_token=token), 201

    @app.post("/login")
    @limiter.limit("10 per minute")
    def login():
        payload, error = parse_json(LoginSchema())
        if error:
            return error

        email = payload["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(payload["password"]):
            return jsonify(error="credenciales inválidas"), 401

        token = create_access_token(identity=str(user.id))
        return jsonify(user=user.to_dict(), access_token=token)

    @app.get("/me")
    @jwt_required()
    def me():
        user_id = get_jwt_identity()
        user = db.session.get(User, int(user_id))
        if not user:
            return jsonify(error="usuario no encontrado"), 404
        return jsonify(user=user.to_dict())


app = create_app() if os.environ.get("TESTING") != "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
