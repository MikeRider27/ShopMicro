from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)

from config import Config
from models import User, db

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
jwt = JWTManager(app)
CORS(app)

with app.app_context():
    db.create_all()


@app.get("/health")
def health():
    return jsonify(status="ok", service="auth-service")


@app.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    if not email or not password or not name:
        return jsonify(error="email, password y name son requeridos"), 400
    if len(password) < 6:
        return jsonify(error="la contraseña debe tener al menos 6 caracteres"), 400
    if User.query.filter_by(email=email).first():
        return jsonify(error="el email ya está registrado"), 409

    user = User(email=email, name=name)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify(user=user.to_dict(), access_token=token), 201


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
