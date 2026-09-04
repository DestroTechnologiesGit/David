# nllb-api

[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![python](https://img.shields.io/badge/python-3.8%20|%203.9%20|%203.10%20|%203.11%20|%203.12%20|%203.13%20|%203.14-blue)](https://www.python.org/)
[![main.yml](https://github.com/pbusenius/nllb-api/actions/workflows/main.yml/badge.svg)](https://github.com/pbusenius/nllb-api/actions/workflows/main.yml)
[![cuda.yml](https://github.com/pbusenius/nllb-api/actions/workflows/cuda.yml/badge.svg)](https://github.com/pbusenius/nllb-api/actions/workflows/cuda.yml)
[![clippy.yml](https://github.com/pbusenius/nllb-api/actions/workflows/clippy.yml/badge.svg)](https://github.com/pbusenius/nllb-api/actions/workflows/clippy.yml)
[![client.yml](https://github.com/pbusenius/nllb-api/actions/workflows/client.yml/badge.svg)](https://github.com/pbusenius/nllb-api/actions/workflows/client.yml)
[![formatter.yml](https://github.com/pbusenius/nllb-api/actions/workflows/formatter.yml/badge.svg)](https://github.com/pbusenius/nllb-api/actions/workflows/formatter.yml)

A fast CPU and GPU-accelerated API for Meta's [No Language Left Behind](https://huggingface.co/docs/transformers/model_doc/nllb) distilled 1.3B 8-bit quantised variant. To achieve faster executions, we are using [CTranslate2](https://github.com/OpenNMT/CTranslate2) as our inference engine. The API supports both single and batch translation requests for improved GPU utilization.

> [!IMPORTANT]\
> NLLB was trained with input lengths not exceeding 512 tokens. Translating longer sequences might result in quality degradation. Consider splitting your input into smaller chunks if you begin observing artefacts.

> [!NOTE]\
> NLLB models can sometimes stop generation early, resulting in incomplete translations. The API uses `min_length_percentage` (default: 0.8 / 80%) to prevent this by ensuring a minimum number of output tokens based on input length. **You only need to specify this parameter if you want a value other than 0.8.** See [this discussion](https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6) for more details.

## Self-Hosting

You can self-host the API and access the Swagger UI at [localhost:49494/api/schema/swagger](http://localhost:49494/api/schema/swagger) with the following minimal configuration:

```bash
docker run --rm \
  -e SERVER_PORT=49494 \
  -p 49494:49494 \
  pbusenius/nllb-api:main
```

### API Examples

The `source` and `target` languages must be specified using FLORES-200 codes (e.g., `eng_Latn`, `spa_Latn`, `fra_Latn`).

#### Single Translation

**GET Request:**
```bash
curl 'http://localhost:49494/api/translator?text=Hello%20world&source=eng_Latn&target=spa_Latn'
```

**POST Request:**
```bash
curl -X POST 'http://localhost:49494/api/translator' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "Hello, world!",
    "source": "eng_Latn",
    "target": "spa_Latn"
  }'
```

**Note:** The `min_length_percentage` parameter is optional and defaults to 0.8 (80%). You only need to specify it if you want a different value. This parameter controls the minimum decoding length as a percentage of input tokens to prevent early stopping in NLLB models. See [this discussion](https://huggingface.co/facebook/nllb-200-distilled-600M/discussions/6) for more details.

**Response:**
```json
{
  "result": "¡Hola, mundo!"
}
```

#### Batch Translation

For improved GPU utilization, use batch translation:

```bash
curl -X POST 'http://localhost:49494/api/translator/batch' \
  -H 'Content-Type: application/json' \
  -d '{
    "translations": [
      {"text": "Hello, world!", "source": "eng_Latn", "target": "spa_Latn"},
      {"text": "Bonjour le monde!", "source": "fra_Latn", "target": "eng_Latn"},
      {"text": "Hola, mundo!", "source": "spa_Latn", "target": "deu_Latn"}
    ]
  }'
```

**Note:** The `min_length_percentage` parameter is optional and defaults to 0.8 (80%) for each item. You only need to specify it if you want a different value. Each item computes its minimum decoding length independently based on its own input token count and percentage value.

**Response:**
```json
{
  "results": [
    {"result": "¡Hola, mundo!"},
    {"result": "Hello, world!"},
    {"result": "Hallo, Welt!"}
  ]
}
```

#### Streaming Translation

Stream translations as Server-Sent Events:

```bash
curl -N 'http://localhost:49494/api/translator/stream?text=Hello%20world&source=eng_Latn&target=spa_Latn'
```

**Note:** The `min_length_percentage` query parameter is optional and defaults to 0.8 (80%). You only need to specify it if you want a different value.

#### Language Detection

Detect the source language:

```bash
curl 'http://localhost:49494/api/language?text=Hello%20world'
```

**Response:**
```json
{
  "language": "eng_Latn",
  "confidence": 0.99
}
```

#### Token Counting

Count tokens in text:

```bash
curl 'http://localhost:49494/api/translator/tokens?text=Hello%20world&source=eng_Latn'
```

**Response:**
```json
{
  "tokens": 3
}
```

### Cross-Origin Resource Sharing

You can configure CORS by passing the following environment variables:

```bash
docker run --rm \
  -e SERVER_PORT=49494 \
  -e ACCESS_CONTROL_ALLOW_ORIGIN=localhost,example.com \
  -e ACCESS_CONTROL_ALLOW_CREDENTIALS=true \
  -e ACCESS_CONTROL_ALLOW_HEADERS=X-Custom-Header,Upgrade-Insecure-Requests \
  -e ACCESS_CONTROL_EXPOSE_HEADERS=Content-Encoding,Kuma-Revision \
  -e ACCESS_CONTROL_MAX_AGE=3600 \
  -e ACCESS_CONTROL_ALLOW_METHOD_GET=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_POST=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_OPTIONS=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_PUT=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_DELETE=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_PATCH=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_HEAD=true \
  -e ACCESS_CONTROL_ALLOW_METHOD_TRACE=true \
  -p 49494:49494 \
  pbusenius/nllb-api:main
```

### Optimisation

You can pass the following environment variables to optimise the API for your own uses:

- `MODEL_SIZE`: Model size preset - `small` (600M), `medium` (1.3B), or `large` (3.3B). Defaults to `medium` if not set.
  - `small`: `OpenNMT/nllb-200-distilled-600M-ct2-int8` - Fastest, smallest model
  - `medium`: `OpenNMT/nllb-200-distilled-1.3B-ct2-int8` - Balanced speed and quality
  - `large`: `OpenNMT/nllb-200-3.3B-ct2-int8` - Best quality, slower inference
- `TRANSLATOR_REPOSITORY`: Explicit Hugging Face model repository (overrides `MODEL_SIZE`). Must be a CTranslate2-compatible NLLB model.
- `OMP_NUM_THREADS`: Increases the number of threads used to translate a given batch of inputs.
- `TRANSLATOR_THREADS`: Increases the number of threads used to handle translate requests in parallel.

It is recommended to not modify `WORKER_COUNT` as spawning multiple workers can lead to increased memory usage and poorer performance.

> [!IMPORTANT]\
> `OMP_NUM_THREADS` $\times$ `TRANSLATOR_THREADS` should not exceed the physical number of cores on your machine.

```bash
# Using MODEL_SIZE preset (recommended)
docker run --rm \
  -e SERVER_PORT=49494 \
  -e MODEL_SIZE=medium \
  -e OMP_NUM_THREADS=6 \
  -e TRANSLATOR_THREADS=2 \
  -e WORKER_COUNT=1 \
  -p 49494:49494 \
  pbusenius/nllb-api:main

# Or using explicit TRANSLATOR_REPOSITORY
docker run --rm \
  -e SERVER_PORT=49494 \
  -e TRANSLATOR_REPOSITORY="OpenNMT/nllb-200-distilled-1.3B-ct2-int8" \
  -e OMP_NUM_THREADS=6 \
  -e TRANSLATOR_THREADS=2 \
  -e WORKER_COUNT=1 \
  -p 49494:49494 \
  pbusenius/nllb-api:main
```

### CUDA Support

You can accelerate your inference with CUDA. First, download the models locally:

```bash
make download-models
```

Then build the CUDA-enabled image:

```bash
make docker-build-cuda
```

After building the image, you can run it with GPU support:

> [!NOTE]\
> `OMP_NUM_THREADS` has no effect when CUDA is enabled. Models are pre-copied into the image and will not be downloaded at runtime.

```bash
docker run --rm --gpus all \
  -e USE_CUDA=True \
  -e SERVER_PORT=49494 \
  -e WORKER_COUNT=1 \
  -p 49494:49494 \
  pbusenius/nllb-api:main-cuda
```

Or use the Makefile target:

```bash
make docker-run-cuda PORT=49494
```

### Telemetry

You can enable OpenTelemetry support by passing the `OTEL_EXPORTER_OTLP_ENDPOINT` environment variable. This enables exporting of traces, metrics and logs to the specified OTLP endpoint.

```bash
docker run --rm \
  -e SERVER_PORT=49494 \
  -e OTEL_RESOURCE_ATTRIBUTES=service.namespace=production,deployment.environment=production \
  -e OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-prod-ap-southeast-1.grafana.net/otlp \
  -e OTEL_EXPORTER_OTLP_HEADERS="Authorization: Basic $OTEL_AUTH_TOKEN" \
  -e OTEL_METRIC_EXPORT_INTERVAL=10000 \
  -p 49494:49494 \
  pbusenius/nllb-api:main
```

## Development

First, install the required dependencies for your editor with the following.

```bash
uv sync
```

### Running the Server

You can run the server locally in several ways:

**Direct execution (requires models to be downloaded):**
```bash
uv run nllb-api
```

**CUDA-enabled execution:**
```bash
uv run nllb-api-cuda
```

**Stub mode (no model downloads, useful for testing):**
```bash
uv run nllb-api-stub
```

**Docker with CPU inference:**
```bash
make docker-build
docker run --rm -e SERVER_PORT=49494 -p 49494:49494 pbusenius/nllb-api:main
```

**Docker with GPU inference:**
```bash
make download-models  # Download models first
make docker-build-cuda
make docker-run-cuda PORT=49494
```

After starting the server, you can access the Swagger UI at [localhost:49494/api/schema/swagger](http://localhost:49494/api/schema/swagger).

### Benchmarking

A benchmark tool is available to compare single vs batch translation performance using FLORES-200 dataset:

```bash
# Compare single vs batch translation
uv run python benchmarks/benchmark.py --batch-size 200 --num-translations 1000

# Run only batch benchmarks
uv run python benchmarks/benchmark.py --batch-only --batch-size 200 --num-translations 1000

# Filter by domain
uv run python benchmarks/benchmark.py --dataset flores --domain technical --batch-size 50
```

See `benchmarks/README.md` for more details.

### Docker Build Cleanup

Clean up Docker build cache and intermediate stages:

```bash
make docker-clean
```
