import logging

from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("order-service")

_CODE_BY_STATUS = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "UNPROCESSABLE_ENTITY",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}


def error_response(code: str, message: str, status_code: int, details=None):
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status_code


def parse_upstream_error(response, fallback_code: str, fallback_message: str):
    """Extrae code/message de un error de otro microservicio (mismo formato
    {"error": {"code", "message"}}) para propagarlo tal cual, en vez de
    perderlo detrás de un mensaje genérico."""
    try:
        body = response.json()
    except ValueError:
        body = {}
    upstream = body.get("error") if isinstance(body, dict) else None
    if isinstance(upstream, dict):
        return upstream.get("code", fallback_code), upstream.get("message", fallback_message)
    return fallback_code, fallback_message


def register_error_handlers(app) -> None:
    @app.errorhandler(ValidationError)
    def handle_validation_error(err: ValidationError):
        return error_response("VALIDATION_ERROR", "datos inválidos", 400, details=err.messages)

    @app.errorhandler(HTTPException)
    def handle_http_exception(err: HTTPException):
        code = _CODE_BY_STATUS.get(err.code, "ERROR")
        return error_response(code, err.description or err.name, err.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected_error(err: Exception):
        logger.exception("Error interno no manejado")
        return error_response("INTERNAL_ERROR", "ocurrió un error interno", 500)
