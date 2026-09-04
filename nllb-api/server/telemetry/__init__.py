"""
OpenTelemetry instrumentation setup for monitoring API calls and performance metrics.
"""
import os
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from server.logging_config import get_logger
from server.telemetry.log_handler import get_log_handler as get_log_handler
from server.telemetry.meter_provider import (
    get_meter_provider as get_meter_provider,
    get_prometheus_metric_reader as get_prometheus_metric_reader,
)
from server.telemetry.tracer_provider import get_tracer_provider as get_tracer_provider

# Global reference to the Prometheus metric reader
_prometheus_metric_reader: Optional[PrometheusMetricReader] = None

logger = get_logger(__name__)


def setup_telemetry(app, service_name: Optional[str] = None):
    """
    Set up OpenTelemetry instrumentation for the FastAPI application.

    Args:
        app: FastAPI application instance
        service_name: Optional service name override
    """
    global _prometheus_metric_reader

    config = app.state.config
    app_id: str = app.state.app_id

    if not config.otel_enabled:
        return

    service_name = service_name or config.app_name

    # Set up tracing if OTLP endpoint is configured
    if config.otel_exporter_otlp_endpoint:
        tracer_provider = get_tracer_provider(otlp_service_name=service_name, otlp_service_instance_id=app_id)
        trace.set_tracer_provider(tracer_provider)

        # Add console exporter for traces (useful for debugging)
        if os.getenv("OTEL_LOG_LEVEL", "").lower() == "debug":
            console_exporter = ConsoleSpanExporter()
            span_processor = BatchSpanProcessor(console_exporter)
            tracer_provider.add_span_processor(span_processor)

    # Set up metrics with Prometheus exporter
    meter_provider = get_meter_provider(
        otlp_service_name=service_name,
        otlp_service_instance_id=app_id,
        use_prometheus=True,
    )
    metrics.set_meter_provider(meter_provider)
    _prometheus_metric_reader = get_prometheus_metric_reader()

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    logger.info("OpenTelemetry instrumentation enabled", service_name=service_name, app_id=app_id)


def get_metrics_reader() -> Optional[PrometheusMetricReader]:
    """
    Get the Prometheus metric reader for exposing metrics endpoint.

    Returns:
        PrometheusMetricReader instance if telemetry is enabled, None otherwise
    """
    return _prometheus_metric_reader
