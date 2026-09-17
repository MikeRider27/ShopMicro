import os


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
            "CORS_ORIGINS": "*",
            "ADMIN_API_KEY": "test-admin-key",
            "RATELIMIT_STORAGE_URI": "memory://",
        }

    host = require_env("POSTGRES_HOST")
    port = require_env("POSTGRES_PORT")
    user = require_env("POSTGRES_USER")
    password = require_env("POSTGRES_PASSWORD")
    name = require_env("POSTGRES_DB")
    admin_key = require_env("ADMIN_API_KEY")
    cors_origins = [o.strip() for o in require_env("CORS_ALLOWED_ORIGINS").split(",") if o.strip()]
    redis_url = require_env("REDIS_URL")

    return {
        "TESTING": False,
        "SQLALCHEMY_DATABASE_URI": (
            f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "CORS_ORIGINS": cors_origins,
        "ADMIN_API_KEY": admin_key,
        "RATELIMIT_STORAGE_URI": redis_url,
    }
