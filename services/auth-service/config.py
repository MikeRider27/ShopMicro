import os
from datetime import timedelta


class Config:
    POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "192.168.11.220")
    POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5436")
    POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "123")
    POSTGRES_DB = os.environ.get("POSTGRES_DB", "ecommerce_auth")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
