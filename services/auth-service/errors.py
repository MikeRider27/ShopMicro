import logging

from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import HTTPException

logger = logging.getLogger("auth-service")

# Códigos genéricos para excepciones que no pasan por un `error_response()`
# explícito (rutas no encontradas, 405, rate limit, etc). Los errores de
# negocio (ej. "el email ya está registrado") usan un code específico, ver
# los `return error_response(...)` en app.py.
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
    """Formato de error único para todo el servicio:
    {"error": {"code": "...", "message": "...", "details": {...opcional...}}}
    """
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status_code


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
        # No exponer el mensaje/traceback real al cliente (puede contener SQL,
        # rutas internas, etc.); se loguea completo para poder debuggear.
        logger.exception("Error interno no manejado")
        return error_response("INTERNAL_ERROR", "ocurrió un error interno", 500)
