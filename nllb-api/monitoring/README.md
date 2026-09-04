# Monitoring

This directory contains Grafana dashboard configurations for monitoring NLLB-API.

## Grafana Dashboard

### Import Dashboard

1. Open Grafana UI
2. Go to **Dashboards** → **Import**
3. Upload `grafana-dashboard.json` or paste its contents
4. Select your Prometheus data source
5. Click **Import**

### Dashboard Panels

1. **API Calls Rate** - Shows requests per second over time
2. **Response Latency (P99/P95/P50)** - Shows P99, P95, and P50 latency percentiles over time
3. **Total API Calls** - Cumulative request count over the last hour
4. **HTTP Status Codes** - Request rate by HTTP status code (2xx, 4xx, 5xx)
5. **CPU Utilization** - CPU usage percentage
6. **Memory Usage** - Memory and virtual memory usage
7. **Batch Size Distribution** - Shows batch size percentiles and request rate by batch size
8. **Batch vs Single Translation Requests** - Compares batch endpoint vs single translation endpoint usage
9. **GPU Utilization** - GPU and GPU memory utilization percentage (if GPU available)
10. **GPU Memory Usage** - GPU memory usage (used, free, total) (if GPU available)
11. **GPU Temperature** - GPU temperature in Celsius (if GPU available)
12. **GPU Power Usage** - GPU power consumption in Watts (if GPU available)

### Prometheus Queries Used

- **Request Rate**: `sum(rate(http_server_request_duration_count{service_name="nllb-api"}[5m]))`
- **P99 Latency**: `histogram_quantile(0.99, sum(rate(http_server_request_duration_bucket{service_name="nllb-api"}[5m])) by (le))`
- **P95 Latency**: `histogram_quantile(0.95, sum(rate(http_server_request_duration_bucket{service_name="nllb-api"}[5m])) by (le))`
- **P50 Latency**: `histogram_quantile(0.50, sum(rate(http_server_request_duration_bucket{service_name="nllb-api"}[5m])) by (le))`
- **Total Requests**: `sum(increase(http_server_request_duration_count{service_name="nllb-api"}[1h]))`
- **HTTP 2xx**: `sum(rate(http_server_request_duration_count{service_name="nllb-api",http_status_code=~"2.."}[5m]))`
- **HTTP 4xx**: `sum(rate(http_server_request_duration_count{service_name="nllb-api",http_status_code=~"4.."}[5m]))`
- **HTTP 5xx**: `sum(rate(http_server_request_duration_count{service_name="nllb-api",http_status_code=~"5.."}[5m]))`
- **CPU Utilization**: `process_runtime_cpython_cpu_utilization{app="nllb-api"} * 100`
- **Memory Usage**: `process_memory_usage_bytes{app="nllb-api"}`
- **Virtual Memory**: `process_memory_virtual_bytes{app="nllb-api"}`
- **Batch Size P50**: `histogram_quantile(0.50, sum(rate(nllb_api_batch_size_bucket{app="nllb-api"}[5m])) by (le, batch_size_bucket))`
- **Batch Size P95**: `histogram_quantile(0.95, sum(rate(nllb_api_batch_size_bucket{app="nllb-api"}[5m])) by (le, batch_size_bucket))`
- **Batch Size P99**: `histogram_quantile(0.99, sum(rate(nllb_api_batch_size_bucket{app="nllb-api"}[5m])) by (le, batch_size_bucket))`
- **Batch Requests by Size**: `sum(rate(nllb_api_batch_size_count{app="nllb-api"}[5m])) by (batch_size_bucket)`
- **Batch Endpoint Rate**: `sum(rate(http_server_duration_milliseconds_count{app="nllb-api",http_route="/api/translator/batch"}[5m]))`
- **Single Translation Rate**: `sum(rate(http_server_duration_milliseconds_count{app="nllb-api",http_route=~"/api/translator[^/]"}[5m]))`
- **GPU Utilization**: `DCGM_FI_DEV_GPU_UTIL{container="nllb-api"}`
- **GPU Memory Copy Utilization**: `DCGM_FI_DEV_MEM_COPY_UTIL{container="nllb-api"}`
- **GPU Memory Used**: `DCGM_FI_DEV_FB_USED{container="nllb-api"}`
- **GPU Memory Free**: `DCGM_FI_DEV_FB_FREE{container="nllb-api"}`
- **GPU Memory Total**: `DCGM_FI_DEV_FB_TOTAL{container="nllb-api"}`
- **GPU Temperature**: `DCGM_FI_DEV_GPU_TEMP{container="nllb-api"}`
- **GPU Power Usage**: `DCGM_FI_DEV_POWER_USAGE{container="nllb-api"}`

### Troubleshooting

If you don't see any data in the dashboard:

1. **Check if metrics are being scraped**: Query Prometheus directly:
   ```promql
   up{job="nllb-api"}
   ```

2. **List available metrics**: Check what metrics are available:
   ```promql
   {__name__=~".*http.*",service_name="nllb-api"}
   ```

3. **Verify service name label**: The label should be `service_name`, not `service`. Check available labels:
   ```promql
   {service_name="nllb-api"}
   ```

4. **Check metrics endpoint**: Verify the `/api/metrics` endpoint is accessible and returns data:
   ```bash
   curl http://nllb-api.forensic-tools.svc.cluster.local/api/metrics
   ```

### Requirements

- Prometheus data source configured in Grafana
- Prometheus scraping NLLB-API service (configured via ServiceMonitor or Service annotations)
- Service label: `service_name="nllb-api"` (OpenTelemetry uses `service_name` label)
- OpenTelemetry enabled in NLLB-API (`OTEL_ENABLED=true`)

### Kubernetes Service Annotations

To enable Prometheus scraping, add these annotations to your Service:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "7860"
    prometheus.io/path: "/api/metrics"
```

### ServiceMonitor (Prometheus Operator)

Alternatively, create a ServiceMonitor resource:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: nllb-api
  namespace: forensic-tools
  labels:
    app: nllb-api
spec:
  selector:
    matchLabels:
      app: nllb-api
  endpoints:
    - port: http
      path: /api/metrics
      interval: 30s
      scrapeTimeout: 10s
```

