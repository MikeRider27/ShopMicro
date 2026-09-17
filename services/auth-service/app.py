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

from config import build_config
from errors import error_response, register_error_handlers
from middleware import register_request_id
from models import User, db
from schemas import LoginSchema, RegisterSchema


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
    register_request_id(app, "auth-service")

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


def register_jwt_error_handlers(jwt: JWTManager) -> None:
    """Mismo formato de error para fallas de JWT que para el resto del
    servicio (por default, flask-jwt-extended devuelve {"msg": "..."})."""

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response("MISSING_TOKEN", "se requiere un token de autenticación", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response("INVALID_TOKEN", "token inválido", 422)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response("TOKEN_EXPIRED", "el token expiró, iniciá sesión de nuevo", 401)


def register_routes(app: Flask, limiter: Limiter) -> None:
    @app.get("/health")
    def health():
        return jsonify(status="ok", service="auth-service")

    @app.post("/register")
    @limiter.limit("10 per minute")
    def register():
        payload = RegisterSchema().load(request.get_json(silent=True) or {})

        email = payload["email"].strip().lower()
        name = payload["name"].strip()

        if User.query.filter_by(email=email).first():
            return error_response("EMAIL_ALREADY_REGISTERED", "el email ya está registrado", 409)

        user = User(email=email, name=name)
        user.set_password(payload["password"])
        db.session.add(user)
        db.session.commit()

        token = create_access_token(identity=str(user.id))
        return jsonify(user=user.to_dict(), access_token=token), 201

    @app.post("/login")
    @limiter.limit("10 per minute")
    def login():
        payload = LoginSchema().load(request.get_json(silent=True) or {})

        email = payload["email"].strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(payload["password"]):
            return error_response("INVALID_CREDENTIALS", "credenciales inválidas", 401)

        token = create_access_token(identity=str(user.id))
        return jsonify(user=user.to_dict(), access_token=token)

    @app.get("/me")
    @jwt_required()
    def me():
        user_id = get_jwt_identity()
        user = db.session.get(User, int(user_id))
        if not user:
            return error_response("USER_NOT_FOUND", "usuario no encontrado", 404)
        return jsonify(user=user.to_dict())


app = create_app() if os.environ.get("TESTING") != "1" else None

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
