import time

from flask import Flask, Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Cantidad total de requests HTTP",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duración de los requests HTTP en segundos",
    ["method", "endpoint"],
)

REQUEST_ERRORS = Counter(
    "http_request_errors_total",
    "Cantidad de requests HTTP que terminaron en error (status >= 400)",
    ["method", "endpoint", "status"],
)


def register_metrics(app: Flask) -> None:
    """Expone métricas básicas de requests/errores/tiempos de respuesta en
    GET /metrics, en formato Prometheus (texto plano, `# TYPE`/`# HELP` +
    series). No requiere infraestructura extra: cualquier Prometheus puede
    scrapear este endpoint directamente."""

    @app.before_request
    def _start_timer():
        g._metrics_started_at = time.monotonic()

    @app.after_request
    def _record_metrics(response):
        if request.path == "/metrics":
            return response

        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        started_at = g.get("_metrics_started_at")
        duration = time.monotonic() - started_at if started_at else 0

        REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
        REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)
        if response.status_code >= 400:
            REQUEST_ERRORS.labels(request.method, endpoint, response.status_code).inc()

        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
