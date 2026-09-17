import logging
import uuid

from flask import Flask, g, has_request_context, request


class RequestIdFilter(logging.Filter):
    """Inyecta el request_id actual en cada log record, para poder
    correlacionar líneas de log de un mismo request (incluso entre
    microservicios distintos, ver X-Request-ID)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = g.request_id if has_request_context() and "request_id" in g else "-"
        return True


def register_request_id(app: Flask, logger_name: str) -> None:
    @app.before_request
    def _set_request_id():
        # Si el gateway (o quien llame) ya mandó uno, lo respetamos: así se
        # puede seguir un mismo request a través de varios servicios.
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    @app.after_request
    def _echo_request_id(response):
        response.headers["X-Request-ID"] = g.get("request_id", "-")
        return response

    logger = logging.getLogger(logger_name)
    if not any(isinstance(f, RequestIdFilter) for f in logger.filters):
        logger.addFilter(RequestIdFilter())
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(request_id)s] %(levelname)s in %(name)s: %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
