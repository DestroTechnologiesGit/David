from collections.abc import Iterable
from os import statvfs
from pathlib import Path
from typing import TYPE_CHECKING

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.metrics import CallbackOptions, Meter, Observation, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_INSTANCE_ID, SERVICE_NAME, OTELResourceDetector, Resource

if TYPE_CHECKING:
    from typing import Optional


def get_system_filesystem_usage(_: CallbackOptions) -> Iterable[Observation]:
    """
    Summary
    -------
    callback function to observe system filesystem usage metrics

    Parameters
    ----------
    options (CallbackOptions)
        callback options

    Yields
    ------
    observation (Observation)
        an observation of filesystem usage with associated labels
    """
    with Path("/proc/mounts").open() as mounts:
        mount = next(root_mount for mount in mounts if (root_mount := mount.split())[1] == "/")

    usage = statvfs("/")
    device, mountpoint, filesystem_type, filesystem_mode, *__ = mount
    labels_base = {
        "system.filesystem.device": device,
        "system.filesystem.mountpoint": mountpoint,
        "system.filesystem.type": filesystem_type,
        "system.filesystem.mode": filesystem_mode,
    }

    labels_used = {**labels_base, "system.filesystem.state": "used"}
    yield Observation(usage.f_bfree, labels_used)

    labels_free = {**labels_base, "system.filesystem.state": "free"}
    yield Observation(usage.f_bavail, labels_free)

    labels_reserved = {**labels_base, "system.filesystem.state": "reserved"}
    yield Observation(usage.f_bsize * (usage.f_blocks - usage.f_bfree - usage.f_bavail), labels_reserved)


# Global reference to the Prometheus metric reader
_prometheus_metric_reader: "Optional[PrometheusMetricReader]" = None


def get_meter_provider(
    *, otlp_service_name: str, otlp_service_instance_id: str, use_prometheus: bool = True
) -> MeterProvider:
    """
    Summary
    -------
    creates and configures a MeterProvider for OpenTelemetry metrics with Prometheus and/or OTLP exporter

    Parameters
    ----------
    otlp_service_name (str)
        the service name to be used in the OpenTelemetry resource

    otlp_service_instance_id (str)
        the service instance ID to be used in the OpenTelemetry resource

    use_prometheus (bool)
        whether to use Prometheus exporter (default: True)

    Returns
    -------
    meter_provider (MeterProvider)
        the configured MeterProvider instance
    """
    global _prometheus_metric_reader

    system_metrics_config = {
        "process.cpu.time": ["user", "system"],
        "process.cpu.utilization": None,
        "process.memory.usage": None,
        "process.memory.virtual": None,
        "process.runtime.memory": ["rss", "vms"],
        "process.runtime.cpu.time": ["user", "system"],
        "process.runtime.gc_count": None,
        "cpython.gc.collections": None,
        "process.runtime.thread_count": None,
        "process.runtime.cpu.utilization": None,
        "system.filesystem.usage": None,
    }

    resource = Resource({SERVICE_NAME: otlp_service_name, SERVICE_INSTANCE_ID: otlp_service_instance_id})
    merged_resource = resource.merge(OTELResourceDetector().detect())

    metric_readers = []
    if use_prometheus:
        _prometheus_metric_reader = PrometheusMetricReader()
        metric_readers.append(_prometheus_metric_reader)

    meter_provider = MeterProvider(metric_readers, merged_resource)
    system_metrics_instrumentor = SystemMetricsInstrumentor(config=system_metrics_config)
    system_metrics_instrumentor.instrument(meter_provider=meter_provider)

    if isinstance(meter := system_metrics_instrumentor._meter, Meter):
        meter.create_observable_up_down_counter(
            "system.filesystem.usage",
            [get_system_filesystem_usage],
            "By",
            "System filesystem usage",
        )
        # Note: GPU metrics are provided by DCGM exporter in Kubernetes
        # and are queried directly from Prometheus (see grafana-dashboard.json)

    set_meter_provider(meter_provider)

    return meter_provider


def get_prometheus_metric_reader() -> "Optional[PrometheusMetricReader]":
    """
    Summary
    -------
    get the Prometheus metric reader for exposing metrics endpoint

    Returns
    -------
    prometheus_metric_reader (Optional[PrometheusMetricReader])
        the PrometheusMetricReader instance if available, None otherwise
    """
    return _prometheus_metric_reader
