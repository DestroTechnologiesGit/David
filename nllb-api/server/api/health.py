from fastapi import APIRouter, Response, status

from server.schemas import Health
from server.telemetry import get_metrics_reader

router = APIRouter()


@router.get("/health", tags=["Monitoring"], response_model=Health)
def health() -> Health:
    """
    Summary
    -------
    the `/health` route will return a shields.io endpoint badge response
    """
    return Health()


@router.get("/metrics", tags=["Monitoring"])
def metrics() -> Response:
    """
    Summary
    -------
    Prometheus metrics endpoint for OpenTelemetry metrics

    Returns
    -------
    response (Response)
        Prometheus-formatted metrics that can be scraped by monitoring systems
    """
    metrics_reader = get_metrics_reader()
    if metrics_reader is None:
        return Response(
            content="OpenTelemetry metrics not enabled",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="text/plain",
        )

    # Get the Prometheus registry from the metric reader
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

    # Access the registry from the PrometheusMetricReader
    # The registry is stored in the _collector attribute
    try:
        registry = metrics_reader._collector._registry
    except AttributeError:
        # Try alternative access pattern
        try:
            registry = metrics_reader._registry
        except AttributeError:
            # Fallback to default registry
            from prometheus_client import REGISTRY

            registry = REGISTRY

    return Response(content=generate_latest(registry=registry), media_type=CONTENT_TYPE_LATEST)
