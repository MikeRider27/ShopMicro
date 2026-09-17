import os

# Único lugar donde vive este valor por defecto (antes estaba repetido en la
# rama de testing y en la de producción). La fuente de verdad real para todo
# despliegue con Docker Compose es la variable de entorno PRODUCT_SERVICE_URL
# en docker-compose.yml; esto es solo el fallback para correr el servicio
# suelto (tests, `flask run` local, etc.).
DEFAULT_PRODUCT_SERVICE_URL = "http://product-service:5002"


class MissingEnvVarError(RuntimeError):
    pass


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingEnvVarError(
            f"La variable de entorno {name} es obligatoria. "
            "Defínela (por ejemplo en tu .env) antes de iniciar el servicio."
        )
    return value


def build_config(testing: bool = False) -> dict:
    if testing:
        return {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "JWT_SECRET_KEY": "test-secret-key-with-enough-length-1234567890",
            "CORS_ORIGINS": "*",
            "PRODUCT_SERVICE_URL": DEFAULT_PRODUCT_SERVICE_URL,
        }

    host = require_env("POSTGRES_HOST")
    port = require_env("POSTGRES_PORT")
    user = require_env("POSTGRES_USER")
    password = require_env("POSTGRES_PASSWORD")
    name = require_env("POSTGRES_DB")
    jwt_secret = require_env("JWT_SECRET_KEY")
    cors_origins = [o.strip() for o in require_env("CORS_ALLOWED_ORIGINS").split(",") if o.strip()]

    return {
        "TESTING": False,
        "SQLALCHEMY_DATABASE_URI": (
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": jwt_secret,
        "CORS_ORIGINS": cors_origins,
        "PRODUCT_SERVICE_URL": os.environ.get("PRODUCT_SERVICE_URL", DEFAULT_PRODUCT_SERVICE_URL),
    }
