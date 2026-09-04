# Redis Caching for Batch Translation

## Overview

This document outlines the implementation plan for adding Redis-based caching to the NLLB API batch translation endpoint. The caching strategy operates at the **per-item level**, allowing efficient handling of partially cached batch requests.

### Configuration
- **Cache Backend**: Redis
- **Configuration**: Full environment variable configuration
- **Response Schema**: Unchanged (no cache metadata)
- **Admin Endpoints**: None

---

## The Problem

Batch caching is non-trivial because:
1. A batch may contain **partially cached** items (some seen before, some new)
2. Cache keys need to account for: `text + source + target + min_length_percentage`
3. We need to efficiently split batches into cached/uncached, translate only the uncached, then reassemble

---

## Architecture

### Cache Flow

```
Batch Request (10 items)
         │
         ▼
┌──────────────────────────┐
│  Generate cache keys     │
│  for each item           │
│  key = hash(text+src+    │
│        tgt+min_len_pct)  │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Check cache for each    │
│  item (bulk lookup)      │
└──────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────────────┐
│Cached: │ │Uncached: 4     │
│6 items │ │items to batch  │
└────────┘ │translate       │
           └────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │ translate_batch│
          │ (only 4 items) │
          └────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │ Store new      │
          │ results in     │
          │ cache          │
          └────────────────┘
                   │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
┌──────────────────────────┐
│  Reassemble results      │
│  in original order       │
│  (cached + new)          │
└──────────────────────────┘
         │
         ▼
    Response (10 results)
```

### Cache Key Design

```python
def generate_cache_key(text: str, source: Language, target: Language, min_length_percentage: float) -> str:
    # Use a hash for fixed-length keys
    content = f"{source}|{target}|{min_length_percentage:.2f}|{text}"
    return hashlib.sha256(content.encode()).hexdigest()
```

---

## Dependencies

Add to `pyproject.toml`:

```toml
dependencies = [
    ...
    "redis>=5.0.0",  # Redis client with async support
]
```

---

## Configuration Settings

Add to `server/settings.py`:

```python
# Cache settings
CACHE_ENABLED: bool = True                         # Enable/disable caching
CACHE_REDIS_URL: str = "redis://localhost:6379/0"  # Redis connection URL
CACHE_TTL: int = 86400                             # Time-to-live in seconds (24h default)
CACHE_MAX_SIZE: int = 100000                       # Max number of cached translations
CACHE_KEY_PREFIX: str = "nllb:"                    # Redis key prefix for namespacing
```

---

## New Files

### `server/features/cache/__init__.py`

Package initialization.

### `server/features/cache/protocol.py`

Defines the interface for cache implementations (allows swapping backends later):

```python
from typing import Protocol

class TranslationCacheProtocol(Protocol):
    def get(self, key: str) -> str | None: ...
    def get_many(self, keys: list[str]) -> dict[str, str | None]: ...
    def set(self, key: str, value: str, ttl: int | None = None) -> None: ...
    def set_many(self, items: dict[str, str], ttl: int | None = None) -> None: ...
    def delete(self, key: str) -> bool: ...
    def clear(self) -> None: ...
    def size(self) -> int: ...
```

### `server/features/cache/redis_cache.py`

Redis implementation of the cache:

```python
import hashlib
import redis
from server.typedefs import Language

class RedisTranslationCache:
    def __init__(self, redis_url: str, prefix: str = "nllb:", ttl: int = 86400, max_size: int = 100000):
        self.client = redis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix
        self.ttl = ttl
        self.max_size = max_size

    @staticmethod
    def generate_key(text: str, source: Language, target: Language, min_length_pct: float) -> str:
        content = f"{source}|{target}|{min_length_pct:.2f}|{text}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_many(self, keys: list[str]) -> dict[str, str | None]:
        if not keys:
            return {}
        prefixed_keys = [f"{self.prefix}{k}" for k in keys]
        values = self.client.mget(prefixed_keys)
        return {k: v for k, v in zip(keys, values)}

    def set_many(self, items: dict[str, str], ttl: int | None = None) -> None:
        if not items:
            return
        pipe = self.client.pipeline()
        effective_ttl = ttl or self.ttl
        for key, value in items.items():
            pipe.setex(f"{self.prefix}{key}", effective_ttl, value)
        pipe.execute()
    
    # ... other methods
```

### `server/features/cache/noop_cache.py`

No-op implementation when caching is disabled:

```python
class NoOpTranslationCache:
    def get_many(self, keys: list[str]) -> dict[str, str | None]:
        return {k: None for k in keys}
    
    def set_many(self, items: dict[str, str], ttl: int | None = None) -> None:
        pass  # Do nothing
    
    # ... other methods return empty/no-op
```

---

## Modified Files

### `server/features/translator/nllb.py`

Integrate caching into batch processing:

```python
def translate_batch(
    self,
    texts: list[str],
    source_languages: list[Language],
    target_languages: list[Language],
    min_length_percentages: list[float] | None = None,
    cache: TranslationCacheProtocol | None = None,
) -> list[str]:
    if not texts:
        return []
    
    if min_length_percentages is None:
        min_length_percentages = [0.8] * len(texts)
    
    # Step 1: Generate cache keys for all items
    cache_keys = [
        RedisTranslationCache.generate_key(text, src, tgt, pct)
        for text, src, tgt, pct in zip(texts, source_languages, target_languages, min_length_percentages)
    ]
    
    # Step 2: Bulk lookup in cache
    results: list[str | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    
    if cache:
        cached_values = cache.get_many(cache_keys)
        for i, key in enumerate(cache_keys):
            if cached_values.get(key) is not None:
                results[i] = cached_values[key]
            else:
                uncached_indices.append(i)
    else:
        uncached_indices = list(range(len(texts)))
    
    # Step 3: Translate only uncached items
    if uncached_indices:
        uncached_texts = [texts[i] for i in uncached_indices]
        uncached_sources = [source_languages[i] for i in uncached_indices]
        uncached_targets = [target_languages[i] for i in uncached_indices]
        uncached_percentages = [min_length_percentages[i] for i in uncached_indices]
        
        # Call actual translation (existing logic)
        translated = self._translate_batch_internal(
            uncached_texts, uncached_sources, uncached_targets, uncached_percentages
        )
        
        # Step 4: Store new translations in cache
        if cache:
            cache_items = {
                cache_keys[uncached_indices[j]]: translated[j]
                for j in range(len(translated))
            }
            cache.set_many(cache_items)
        
        # Step 5: Merge into results
        for j, idx in enumerate(uncached_indices):
            results[idx] = translated[j]
    
    return results  # type: ignore (all None values replaced)
```

### `server/typedefs.py`

Add cache to AppState:

```python
from server.features.cache.redis_cache import RedisTranslationCache
from server.features.cache.noop_cache import NoOpTranslationCache

class AppState:
    translator: TranslatorProtocol
    cache: TranslationCacheProtocol
    
    def __init__(self, settings):
        # ... existing translator setup ...
        
        if settings.cache_enabled:
            self.cache = RedisTranslationCache(
                redis_url=settings.cache_redis_url,
                prefix=settings.cache_key_prefix,
                ttl=settings.cache_ttl,
                max_size=settings.cache_max_size,
            )
        else:
            self.cache = NoOpTranslationCache()
```

### `server/api/translator.py`

Pass cache to translate_batch (around line 170):

```python
translated_texts = state.translator.translate_batch(
    texts, source_languages, target_languages, min_length_percentages,
    cache=state.cache  # Pass cache to translator
)
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Modify | Add `redis>=5.0.0` dependency |
| `server/settings.py` | Modify | Add cache configuration settings |
| `server/features/cache/__init__.py` | Create | Package init |
| `server/features/cache/protocol.py` | Create | Cache interface protocol |
| `server/features/cache/redis_cache.py` | Create | Redis implementation |
| `server/features/cache/noop_cache.py` | Create | No-op fallback |
| `server/features/translator/nllb.py` | Modify | Add cache integration to `translate_batch` |
| `server/typedefs.py` | Modify | Add cache to AppState |
| `server/api/translator.py` | Modify | Pass cache to translate_batch |
| Tests | Create | New tests for cache functionality |

---

## Environment Variables

```bash
# Enable/disable caching
CACHE_ENABLED=true

# Redis connection
CACHE_REDIS_URL=redis://localhost:6379/0

# Cache TTL in seconds (default: 24 hours)
CACHE_TTL=86400

# Maximum number of cached entries
CACHE_MAX_SIZE=100000

# Redis key prefix for namespacing
CACHE_KEY_PREFIX=nllb:
```

---

## Future Enhancements

Potential additions that were not included in this implementation:

1. **Cache stats endpoint**: `GET /translator/cache/stats` - shows hit rate, size, etc.
2. **Cache clear endpoint**: `DELETE /translator/cache` - purges cache (admin only)
3. **Optional bypass**: `?skip_cache=true` query param to force fresh translation
4. **Response metadata**: Include `cached: true/false` in response items
5. **Single translation caching**: Extend caching to single `/translator` endpoints
