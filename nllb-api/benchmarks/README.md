# Benchmark Tools

This directory contains benchmark tools to measure translation API performance using the FLORES-200 evaluation dataset.

## FLORES-200 Dataset

FLORES-200 is a comprehensive multilingual evaluation dataset with 204 languages, designed for standardized machine translation evaluation. The benchmark includes representative samples covering various domains:

- **General**: Common phrases and sentences
- **Technical**: Technology and computing terminology
- **News**: Current events and journalism
- **Science**: Scientific research and discoveries
- **Culture**: Arts, traditions, and cultural topics
- **Social**: Social issues and society
- **Business**: Commerce and economics
- **Environment**: Climate and environmental topics
- **Health**: Healthcare and medical topics
- **Academic**: Educational and scholarly content
- **Technology**: Digital and technological advances

## benchmark.py

Compares single vs batch translation performance using FLORES-200 samples.

### Usage

```bash
# Basic benchmark with FLORES-200 dataset (default)
uv run python benchmarks/benchmark.py

# Custom configuration
uv run python benchmarks/benchmark.py \
    --base-url http://localhost:49494/api \
    --num-translations 200 \
    --batch-size 20 \
    --iterations 5 \
    --warmup 10

# Use simple test data instead of FLORES
uv run python benchmarks/benchmark.py --dataset simple

# Filter by domain
uv run python benchmarks/benchmark.py --domain technical
uv run python benchmarks/benchmark.py --domain science --num-translations 50
```

### Options

- `--base-url`: Base URL of the API (default: http://localhost:49494/api)
- `--num-translations`: Total number of translations to perform (default: 100)
- `--batch-size`: Batch size for batch translation (default: 10)
- `--iterations`: Number of benchmark iterations (default: 3)
- `--warmup`: Number of warmup requests (default: 5)
- `--dataset`: Dataset to use - `flores` (default) or `simple`
- `--domain`: Filter FLORES samples by domain (optional)

### Metrics

The benchmark measures:
- **Throughput**: Translations per second
- **Latency**: Average, P50, P95, P99 latencies in milliseconds
- **Improvement**: Percentage improvement of batch over single

### Example Output

```
Benchmark Configuration:
  Base URL: http://localhost:49494/api
  Dataset: flores
  Total translations: 100
  Batch size: 10
  Iterations: 3
  Warmup requests: 5

RESULTS
============================================================

Single Translation (averaged over 3 iterations):
  Throughput: 15.23 translations/sec
  Avg latency: 65.67ms

Batch Translation (batch_size=10, averaged over 3 iterations):
  Throughput: 45.67 translations/sec
  Avg latency: 21.90ms

Improvement:
  Throughput: +199.87%
  Latency: +66.66%
```

## flores_data.py

Provides FLORES-200 sample data for benchmarking. Includes:

- Representative sentences from multiple domains
- Various language pairs (English ↔ 10+ languages, cross-language pairs)
- Realistic sentence lengths and complexity
- Domain categorization for targeted testing

### Available Domains

- `general`: Basic phrases and common sentences
- `technical`: Technology and computing
- `news`: News and current events
- `science`: Scientific content
- `culture`: Cultural topics
- `social`: Social issues
- `business`: Business and economics
- `environment`: Environmental topics
- `health`: Healthcare
- `academic`: Academic content
- `technology`: Digital technology

## References

- FLORES-200: https://github.com/facebookresearch/flores
- NLLB Paper: https://arxiv.org/abs/2207.04672

