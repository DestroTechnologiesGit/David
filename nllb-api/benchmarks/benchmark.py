#!/usr/bin/env python3
"""
Benchmark tool to compare single vs batch translation performance.

This script measures:
- Throughput (translations per second)
- Latency (time per translation)
- GPU utilization (if available)
- Memory usage

Uses FLORES-200 benchmark dataset for realistic evaluation.

Usage:
    uv run python benchmarks/benchmark.py --batch-size 10 --iterations 5
    uv run python benchmarks/benchmark.py --dataset flores --num-translations 200
"""

import argparse
import asyncio
import statistics
import time
from collections.abc import Sequence
from typing import Any

import httpx

from benchmarks.flores_data import get_flores_samples, get_flores_by_domain


class BenchmarkError(Exception):
    """Exception raised when a non-200 status code is encountered."""
    
    def __init__(self, status_code: int, error_detail: str, request_info: dict[str, Any]):
        self.status_code = status_code
        self.error_detail = error_detail
        self.request_info = request_info
        super().__init__(f"HTTP {status_code}: {error_detail}")


class BenchmarkResult:
    """Results from a benchmark run."""

    def __init__(
        self,
        name: str,
        total_time: float,
        num_translations: int,
        latencies: list[float],
    ) -> None:
        self.name = name
        self.total_time = total_time
        self.num_translations = num_translations
        self.latencies = latencies

    @property
    def throughput(self) -> float:
        """Translations per second."""
        return self.num_translations / self.total_time if self.total_time > 0 else 0.0

    @property
    def avg_latency(self) -> float:
        """Average latency in milliseconds."""
        return statistics.mean(self.latencies) * 1000 if self.latencies else 0.0

    @property
    def p50_latency(self) -> float:
        """50th percentile latency in milliseconds."""
        return statistics.median(self.latencies) * 1000 if self.latencies else 0.0

    @property
    def p95_latency(self) -> float:
        """95th percentile latency in milliseconds."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index] * 1000

    @property
    def p99_latency(self) -> float:
        """99th percentile latency in milliseconds."""
        if not self.latencies:
            return 0.0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[index] * 1000

    def __str__(self) -> str:
        return f"""
{self.name}:
  Total time: {self.total_time:.2f}s
  Translations: {self.num_translations}
  Throughput: {self.throughput:.2f} translations/sec
  Avg latency: {self.avg_latency:.2f}ms
  P50 latency: {self.p50_latency:.2f}ms
  P95 latency: {self.p95_latency:.2f}ms
  P99 latency: {self.p99_latency:.2f}ms
"""


def generate_test_data(num_items: int) -> list[dict[str, Any]]:
    """Generate test translation data."""
    test_texts = [
        ("Hello, world!", "eng_Latn", "spa_Latn"),
        ("Bonjour le monde!", "fra_Latn", "eng_Latn"),
        ("Hola, mundo!", "spa_Latn", "eng_Latn"),
        ("Guten Tag, Welt!", "deu_Latn", "eng_Latn"),
        ("Ciao, mondo!", "ita_Latn", "eng_Latn"),
        ("Olá, mundo!", "por_Latn", "eng_Latn"),
        ("Привет, мир!", "rus_Cyrl", "eng_Latn"),
        ("こんにちは、世界！", "jpn_Jpan", "eng_Latn"),
        ("你好，世界！", "zho_Hans", "eng_Latn"),
        ("مرحبا بالعالم!", "arb_Latn", "eng_Latn"),
    ]

    # Repeat test texts to reach num_items
    result = []
    for i in range(num_items):
        text, source, target = test_texts[i % len(test_texts)]
        result.append({"text": text, "source": source, "target": target})

    return result


async def _single_request(
    client: httpx.AsyncClient,
    base_url: str,
    item: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> tuple[float, dict[str, Any] | None]:
    """Make a single translation request."""
    async with semaphore:
        request_start = time.time()
        try:
            response = await client.get(
                f"{base_url}/translator",
                params={
                    "text": item["text"],
                    "source": item["source"],
                    "target": item["target"],
                },
            )
            request_end = time.time()
            
            # Check status code explicitly - stop benchmark if not 200
            if response.status_code != 200:
                error_detail = str(response.text)
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        error_detail = error_json.get("detail", error_json.get("message", error_detail))
                except Exception:
                    pass
                
                request_info = {
                    "text": item["text"][:50] + "..." if len(item["text"]) > 50 else item["text"],
                    "source": item["source"],
                    "target": item["target"],
                    "status": response.status_code,
                    "error": error_detail,
                }
                raise BenchmarkError(response.status_code, error_detail, request_info)
            
            return request_end - request_start, None
        except BenchmarkError:
            # Re-raise BenchmarkError to stop the benchmark
            raise
        except httpx.HTTPStatusError as e:
            request_end = time.time()
            error_detail = str(e)
            try:
                error_json = e.response.json()
                if isinstance(error_json, dict):
                    error_detail = error_json.get("detail", error_json.get("message", str(e)))
            except Exception:
                pass
            
            request_info = {
                "text": item["text"][:50] + "..." if len(item["text"]) > 50 else item["text"],
                "source": item["source"],
                "target": item["target"],
                "status": e.response.status_code,
                "error": error_detail,
            }
            raise BenchmarkError(e.response.status_code, error_detail, request_info)
        except Exception as e:
            request_end = time.time()
            request_info = {
                "text": item["text"][:50] + "..." if len(item["text"]) > 50 else item["text"],
                "source": item["source"],
                "target": item["target"],
                "error": str(e),
            }
            # Treat other exceptions as 500 errors
            raise BenchmarkError(500, str(e), request_info)


async def benchmark_single(
    client: httpx.AsyncClient,
    base_url: str,
    test_data: Sequence[dict[str, Any]],
    workers: int = 1,
) -> BenchmarkResult:
    """Benchmark single translation requests."""
    latencies = []
    errors = []

    start_time = time.time()

    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(workers)

    # Create all tasks
    tasks = [
        _single_request(client, base_url, item, semaphore)
        for item in test_data
    ]

    # Execute all requests concurrently
    # If any request fails with non-200, BenchmarkError will be raised
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except BenchmarkError as e:
        # This shouldn't happen with return_exceptions=True, but handle it anyway
        raise

    # Process results - check for BenchmarkError exceptions
    for idx, result in enumerate(results):
        if isinstance(result, BenchmarkError):
            # Stop benchmark on first error
            raise result
        elif isinstance(result, Exception):
            # Other exceptions should have been converted to BenchmarkError
            raise BenchmarkError(500, str(result), {"item_index": idx})
        else:
            latency, error_info = result
            latencies.append(latency)
            if error_info:
                errors.append(error_info)

    total_time = time.time() - start_time

    result = BenchmarkResult("Single Translation", total_time, len(test_data), latencies)
    result.errors = errors  # type: ignore[attr-defined]
    return result


async def _batch_request(
    client: httpx.AsyncClient,
    base_url: str,
    batch: Sequence[dict[str, Any]],
    batch_start: int,
    semaphore: asyncio.Semaphore,
) -> tuple[float, int, dict[str, Any] | None]:
    """Make a batch translation request."""
    async with semaphore:
        request_start = time.time()
        batch_request = {
            "translations": [
                {"text": item["text"], "source": item["source"], "target": item["target"]}
                for item in batch
            ]
        }

        try:
            response = await client.post(
                f"{base_url}/translator/batch",
                json=batch_request,
            )
            request_end = time.time()
            
            # Check status code explicitly - stop benchmark if not 200
            if response.status_code != 200:
                error_detail = response.text or f"HTTP {response.status_code}"
                try:
                    error_json = response.json()
                    if isinstance(error_json, dict):
                        error_detail = error_json.get("detail", error_json.get("message", error_detail))
                        # Include full error JSON if available
                        if error_json:
                            error_detail = f"{error_detail}\nFull error: {error_json}"
                except Exception:
                    # If JSON parsing fails, use text response
                    if response.text:
                        error_detail = response.text[:500]  # Limit length
                
                request_info = {
                    "batch_start": batch_start,
                    "batch_size": len(batch),
                    "status": response.status_code,
                    "error": error_detail,
                    "language_pairs": [(item["source"], item["target"]) for item in batch],
                    "sample_texts": [item["text"][:50] + "..." if len(item["text"]) > 50 else item["text"] for item in batch[:3]],
                }
                raise BenchmarkError(response.status_code, error_detail, request_info)
            
            # Latency per item in batch
            batch_latency = (request_end - request_start) / len(batch)
            return batch_latency, len(batch), None
        except BenchmarkError:
            # Re-raise BenchmarkError to stop the benchmark
            raise
        except httpx.HTTPStatusError as e:
            request_end = time.time()
            # Try to get error details from response
            error_detail = str(e)
            try:
                error_json = e.response.json()
                if isinstance(error_json, dict):
                    error_detail = error_json.get("detail", error_json.get("message", str(e)))
            except Exception:
                pass
            
            request_info = {
                "batch_start": batch_start,
                "batch_size": len(batch),
                "status": e.response.status_code,
                "error": error_detail,
                "language_pairs": [(item["source"], item["target"]) for item in batch],
            }
            raise BenchmarkError(e.response.status_code, error_detail, request_info)
        except Exception as e:
            request_end = time.time()
            request_info = {
                "batch_start": batch_start,
                "batch_size": len(batch),
                "error": str(e),
                "language_pairs": [(item["source"], item["target"]) for item in batch],
            }
            # Treat other exceptions as 500 errors
            raise BenchmarkError(500, str(e), request_info)


async def benchmark_batch(
    client: httpx.AsyncClient,
    base_url: str,
    test_data: Sequence[dict[str, Any]],
    batch_size: int,
    workers: int = 1,
) -> BenchmarkResult:
    """Benchmark batch translation requests."""
    latencies = []
    errors = []

    start_time = time.time()

    # Create semaphore to limit concurrent batch requests
    semaphore = asyncio.Semaphore(workers)

    # Create batches
    batches = []
    for i in range(0, len(test_data), batch_size):
        batches.append((i, test_data[i : i + batch_size]))

    # Create all tasks
    tasks = [
        _batch_request(client, base_url, batch, batch_start, semaphore)
        for batch_start, batch in batches
    ]

    # Execute all batch requests concurrently
    # If any request fails with non-200, BenchmarkError will be raised
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except BenchmarkError as e:
        # This shouldn't happen with return_exceptions=True, but handle it anyway
        raise

    # Process results - check for BenchmarkError exceptions
    for idx, result in enumerate(results):
        if isinstance(result, BenchmarkError):
            # Stop benchmark on first error
            raise result
        elif isinstance(result, Exception):
            # Other exceptions should have been converted to BenchmarkError
            raise BenchmarkError(500, str(result), {"batch_index": idx})
        else:
            batch_latency, batch_len, error_info = result
            latencies.extend([batch_latency] * batch_len)
            if error_info:
                errors.append(error_info)

    total_time = time.time() - start_time

    result = BenchmarkResult(f"Batch Translation (size={batch_size})", total_time, len(test_data), latencies)
    result.errors = errors  # type: ignore[attr-defined]
    return result


def generate_test_data(num_items: int, dataset: str = "simple") -> list[dict[str, Any]]:
    """
    Generate test translation data.

    Parameters
    ----------
    num_items : int
        Number of test items to generate
    dataset : str
        Dataset to use: 'simple' for basic examples, 'flores' for FLORES-200 samples

    Returns
    -------
    list[dict[str, Any]]
        List of test translation items
    """
    if dataset == "flores":
        return get_flores_samples(num_items)

    # Simple test data (backward compatibility)
    test_texts = [
        ("Hello, world!", "eng_Latn", "spa_Latn"),
        ("Bonjour le monde!", "fra_Latn", "eng_Latn"),
        ("Hola, mundo!", "spa_Latn", "eng_Latn"),
        ("Guten Tag, Welt!", "deu_Latn", "eng_Latn"),
        ("Ciao, mondo!", "ita_Latn", "eng_Latn"),
        ("Olá, mundo!", "por_Latn", "eng_Latn"),
        ("Привет, мир!", "rus_Cyrl", "eng_Latn"),
        ("こんにちは、世界！", "jpn_Jpan", "eng_Latn"),
        ("你好，世界！", "zho_Hans", "eng_Latn"),
        ("مرحبا بالعالم!", "arb_Latn", "eng_Latn"),
    ]

    # Repeat test texts to reach num_items
    result = []
    for i in range(num_items):
        text, source, target = test_texts[i % len(test_texts)]
        result.append({"text": text, "source": source, "target": target})

    return result


async def run_benchmark(
    base_url: str,
    num_translations: int,
    batch_size: int,
    iterations: int,
    warmup: int,
    dataset: str = "flores",
    domain: str | None = None,
    batch_only: bool = False,
    workers: int = 1,
) -> None:
    """Run the benchmark."""
    if domain:
        test_data = get_flores_by_domain(domain)
        if len(test_data) < num_translations:
            # Extend with all FLORES samples if domain filter doesn't have enough
            print(f"Warning: Domain '{domain}' has only {len(test_data)} samples, using all FLORES samples")
            test_data = get_flores_samples(num_translations)
        else:
            test_data = test_data[:num_translations]
    else:
        test_data = generate_test_data(num_translations, dataset=dataset)

    # Validate batch_size
    if batch_size > len(test_data):
        effective_batch_size = len(test_data)
        print(f"⚠️  Warning: Batch size ({batch_size}) is larger than number of translations ({len(test_data)})")
        print(f"   This will result in a single batch with all {len(test_data)} items.")
        print(f"   Consider using --batch-size <= {len(test_data)} to properly test batching.\n")
    else:
        effective_batch_size = batch_size

    print(f"Benchmark Configuration:")
    print(f"  Base URL: {base_url}")
    print(f"  Dataset: {dataset}")
    if domain:
        print(f"  Domain filter: {domain}")
    print(f"  Total translations: {num_translations}")
    print(f"  Batch size: {batch_size}" + (f" (effective: {effective_batch_size})" if batch_size > len(test_data) else ""))
    print(f"  Async workers: {workers}")
    print(f"  Iterations: {iterations}")
    print(f"  Warmup requests: {warmup}")
    print()

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            # Warmup
            if warmup > 0:
                print(f"Warming up with {warmup} requests...")
                warmup_data = test_data[:warmup]
                if not batch_only:
                    await benchmark_single(client, base_url, warmup_data, workers=workers)
                await benchmark_batch(client, base_url, warmup_data, min(effective_batch_size, warmup), workers=workers)
                print("Warmup complete.\n")

            # Run benchmarks
            single_results = []
            batch_results = []

            for iteration in range(iterations):
                print(f"Iteration {iteration + 1}/{iterations}...")

                # Single translation benchmark (skip if batch_only)
                if not batch_only:
                    single_result = await benchmark_single(client, base_url, test_data, workers=workers)
                    single_results.append(single_result)

                # Batch translation benchmark
                batch_result = await benchmark_batch(client, base_url, test_data, effective_batch_size, workers=workers)
                batch_results.append(batch_result)
        except BenchmarkError as e:
            # Stop benchmark and show error details
            print("\n" + "=" * 60)
            print("❌ BENCHMARK STOPPED - Non-200 Status Code Detected")
            print("=" * 60)
            print(f"\nStatus Code: {e.status_code}")
            print(f"\nError Details:")
            print(f"  {e.error_detail}")
            print(f"\nRequest Details:")
            for key, value in e.request_info.items():
                if key == "language_pairs" and isinstance(value, list):
                    print(f"  {key}: {value[:5]}..." if len(value) > 5 else f"  {key}: {value}")
                elif key == "sample_texts" and isinstance(value, list):
                    print(f"  {key}: {value}")
                elif key == "error":
                    # Error already shown above
                    continue
                else:
                    print(f"  {key}: {value}")
            print("\n" + "=" * 60)
            import sys
            sys.exit(1)

        # Aggregate results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)

        if batch_only:
            # Batch-only mode: show only batch results
            avg_batch_throughput = statistics.mean([r.throughput for r in batch_results])
            avg_batch_latency = statistics.mean([r.avg_latency for r in batch_results])
            avg_batch_p50 = statistics.mean([r.p50_latency for r in batch_results])
            avg_batch_p95 = statistics.mean([r.p95_latency for r in batch_results])
            avg_batch_p99 = statistics.mean([r.p99_latency for r in batch_results])

            print("\n" + "=" * 60)
            print("BATCH TRANSLATION RESULTS")
            print("=" * 60)
            print(f"{'Metric':<25} {'Value':>15}")
            print("-" * 60)
            print(f"{'Throughput (trans/sec)':<25} {avg_batch_throughput:>15.2f}")
            print(f"{'Avg Latency (ms)':<25} {avg_batch_latency:>15.2f}")
            print(f"{'P50 Latency (ms)':<25} {avg_batch_p50:>15.2f}")
            print(f"{'P95 Latency (ms)':<25} {avg_batch_p95:>15.2f}")
            print(f"{'P99 Latency (ms)':<25} {avg_batch_p99:>15.2f}")
            print("=" * 60)

            print(f"\n📊 Summary (averaged over {iterations} iterations):")
            print(f"  Throughput: {avg_batch_throughput:.2f} translations/sec")
            print(f"  Average latency: {avg_batch_latency:.2f}ms")
        else:
            # Comparison mode: show single vs batch
            avg_single_throughput = statistics.mean([r.throughput for r in single_results])
            avg_single_latency = statistics.mean([r.avg_latency for r in single_results])
            avg_single_p50 = statistics.mean([r.p50_latency for r in single_results])
            avg_single_p95 = statistics.mean([r.p95_latency for r in single_results])
            avg_single_p99 = statistics.mean([r.p99_latency for r in single_results])

            # Batch translation aggregated
            avg_batch_throughput = statistics.mean([r.throughput for r in batch_results])
            avg_batch_latency = statistics.mean([r.avg_latency for r in batch_results])
            avg_batch_p50 = statistics.mean([r.p50_latency for r in batch_results])
            avg_batch_p95 = statistics.mean([r.p95_latency for r in batch_results])
            avg_batch_p99 = statistics.mean([r.p99_latency for r in batch_results])

            # Calculate improvements
            throughput_improvement = ((avg_batch_throughput - avg_single_throughput) / avg_single_throughput) * 100
            latency_improvement = ((avg_single_latency - avg_batch_latency) / avg_single_latency) * 100
            p50_improvement = ((avg_single_p50 - avg_batch_p50) / avg_single_p50) * 100
            p95_improvement = ((avg_single_p95 - avg_batch_p95) / avg_single_p95) * 100
            p99_improvement = ((avg_single_p99 - avg_batch_p99) / avg_single_p99) * 100

            # Comparison table
            print("\n" + "=" * 85)
            print("COMPARISON: Single vs Batch Translation")
            print("=" * 85)
            print(f"{'Metric':<25} {'Single':>15} {'Batch':>15} {'Improvement':>15}")
            print("-" * 85)
            print(f"{'Throughput (trans/sec)':<25} {avg_single_throughput:>15.2f} {avg_batch_throughput:>15.2f} {throughput_improvement:>14.2f}%")
            print(f"{'Avg Latency (ms)':<25} {avg_single_latency:>15.2f} {avg_batch_latency:>15.2f} {latency_improvement:>14.2f}%")
            print(f"{'P50 Latency (ms)':<25} {avg_single_p50:>15.2f} {avg_batch_p50:>15.2f} {p50_improvement:>14.2f}%")
            print(f"{'P95 Latency (ms)':<25} {avg_single_p95:>15.2f} {avg_batch_p95:>15.2f} {p95_improvement:>14.2f}%")
            print(f"{'P99 Latency (ms)':<25} {avg_single_p99:>15.2f} {avg_batch_p99:>15.2f} {p99_improvement:>14.2f}%")
            print("=" * 85)

            # Summary
            print(f"\n📊 Summary (averaged over {iterations} iterations):")
            print(f"  Batch processing is {throughput_improvement:+.1f}% faster in throughput")
            print(f"  Batch processing reduces latency by {latency_improvement:+.1f}%")
            
            if throughput_improvement > 0:
                speedup = avg_batch_throughput / avg_single_throughput
                print(f"  Speedup factor: {speedup:.2f}x")
            else:
                print(f"  ⚠️  Batch processing is slower - consider adjusting batch size")

        # Error reporting
        all_single_errors = []
        all_batch_errors = []
        if not batch_only:
            for result in single_results:
                if hasattr(result, "errors") and result.errors:
                    all_single_errors.extend(result.errors)
        for result in batch_results:
            if hasattr(result, "errors") and result.errors:
                all_batch_errors.extend(result.errors)

        if all_single_errors or all_batch_errors:
            print(f"\n⚠️  Errors Encountered:")
            if all_single_errors:
                print(f"\n  Single Translation Errors: {len(all_single_errors)}")
                # Group by language pair
                error_pairs: dict[tuple[str, str], int] = {}
                for error in all_single_errors:
                    pair = (error.get("source", "unknown"), error.get("target", "unknown"))
                    error_pairs[pair] = error_pairs.get(pair, 0) + 1
                for (source, target), count in sorted(error_pairs.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {source} → {target}: {count} error(s)")

            if all_batch_errors:
                print(f"\n  Batch Translation Errors: {len(all_batch_errors)} batches")
                # Group errors by status code
                errors_by_status: dict[int, list[dict[str, Any]]] = {}
                for error in all_batch_errors:
                    status = error.get("status", 0)
                    if status not in errors_by_status:
                        errors_by_status[status] = []
                    errors_by_status[status].append(error)
                
                for status_code, status_errors in sorted(errors_by_status.items()):
                    print(f"\n    Status {status_code}: {len(status_errors)} batch(es)")
                    # Show first error detail
                    first_error = status_errors[0]
                    print(f"      Error: {first_error.get('error', 'Unknown error')[:200]}")
                    # Show sample language pairs
                    if status_errors:
                        sample_pairs = status_errors[0].get("language_pairs", [])
                        if sample_pairs:
                            print(f"      Sample language pairs: {sample_pairs[:5]}..." if len(sample_pairs) > 5 else f"      Language pairs: {sample_pairs}")
                    # Show batch indices
                    batch_indices = [e.get("batch_start", "?") for e in status_errors[:10]]
                    if len(status_errors) > 10:
                        print(f"      Batch indices: {batch_indices} ... ({len(status_errors)} total)")
                    else:
                        print(f"      Batch indices: {batch_indices}")

        # Detailed results
        print(f"\nDetailed Results (Iteration 1):")
        if not batch_only:
            print(single_results[0])
        print(batch_results[0])


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Benchmark single vs batch translation performance")
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:49494/api",
        help="Base URL of the API (default: http://localhost:49494/api)",
    )
    parser.add_argument(
        "--num-translations",
        type=int,
        default=100,
        help="Total number of translations to perform (default: 100)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for batch translation (default: 10)",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of benchmark iterations (default: 3)",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=5,
        help="Number of warmup requests (default: 5)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        choices=["simple", "flores"],
        default="flores",
        help="Dataset to use: 'simple' for basic examples, 'flores' for FLORES-200 samples (default: flores)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter FLORES samples by domain (e.g., 'general', 'technical', 'news', 'science', 'culture', 'social', 'business', 'environment', 'health', 'academic', 'technology')",
    )
    parser.add_argument(
        "--batch-only",
        action="store_true",
        help="Run only batch translation benchmarks (skip single translation)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of async workers for concurrent requests (default: 1)",
    )

    args = parser.parse_args()

    asyncio.run(
        run_benchmark(
            base_url=args.base_url,
            num_translations=args.num_translations,
            batch_size=args.batch_size,
            iterations=args.iterations,
            warmup=args.warmup,
            dataset=args.dataset,
            domain=args.domain,
            batch_only=args.batch_only,
            workers=args.workers,
        )
    )


if __name__ == "__main__":
    main()

