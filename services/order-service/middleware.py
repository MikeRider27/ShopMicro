import json
import logging
import time
import uuid

from flask import Flask, g, has_request_context, request

# Atributos "de fábrica" de un LogRecord: todo lo que no esté acá y venga en
# `extra={...}` se considera un campo de negocio (event, order_id, etc.) y se
# vuelca tal cual al JSON. Así log_event() no necesita listar nada a mano.
_STANDARD_LOG_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
}


class RequestIdFilter(logging.Filter):
    """Inyecta el request_id actual en cada log record, para poder
    correlacionar líneas de log de un mismo request (incluso entre
    microservicios distintos, ver X-Request-ID)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = g.request_id if has_request_context() and "request_id" in g else "-"
        return True


class JsonFormatter(logging.Formatter):
    """Logs estructurados: un objeto JSON por línea, parseable por cualquier
    agregador de logs (ELK, Loki, CloudWatch...) sin depender de regex sobre
    texto plano.

    IMPORTANTE: nunca pasar contraseñas, tokens JWT ni API keys en el
    `message` ni en `extra`. Este formatter no redacta nada por su cuenta;
    la responsabilidad de no loguear datos sensibles es de quien llama a
    logger.info/warning/exception (ver los `extra={...}` en app.py de cada
    servicio: solo IDs, cantidades, códigos de error, nunca credenciales).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def register_request_id(app: Flask, logger_name: str) -> None:
    @app.before_request
    def _start_request():
        # Si el gateway (o quien llame) ya mandó uno, lo respetamos: así se
        # puede seguir un mismo request a través de varios servicios.
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g._request_started_at = time.monotonic()

    @app.after_request
    def _finish_request(response):
        response.headers["X-Request-ID"] = g.get("request_id", "-")

        started_at = g.get("_request_started_at")
        duration_ms = round((time.monotonic() - started_at) * 1000, 2) if started_at else None
        endpoint = request.url_rule.rule if request.url_rule else request.path
        # Access log estructurado: SOLO metadata de la request (método, ruta,
        # status, duración). Nunca el body ni headers como Authorization o
        # X-Admin-Key, que sí podrían llegar a tener credenciales.
        logging.getLogger(logger_name).info(
            "http_request",
            extra={
                "event": "http_request",
                "http_method": request.method,
                "http_path": endpoint,
                "http_status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

    logger = logging.getLogger(logger_name)
    if not any(isinstance(f, RequestIdFilter) for f in logger.filters):
        logger.addFilter(RequestIdFilter())
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def log_event(logger_name: str, event: str, **fields) -> None:
    """Loguea un evento de negocio (ej. "order_created", "stock_reserved")
    con el mismo formato JSON estructurado que el resto. `fields` son datos
    de negocio (IDs, cantidades, totales) — nunca contraseñas, tokens ni
    API keys."""
    logging.getLogger(logger_name).info(event, extra={"event": event, **fields})
