ARG PYTHON_VERSION=3.13

# Stage 1: Extract Swagger UI assets
FROM swaggerapi/swagger-ui:v5.9.1 AS swagger-ui

# Stage 2: Copy models from local models/ directory or download (optional)
FROM python:${PYTHON_VERSION}-slim AS model-builder
ARG INCLUDE_MODELS=false
ARG DOWNLOAD_MODELS=false

# Copy models from local models/ directory if available (from make download-models)
# This allows pre-downloading models locally and including them in the image
# Note: COPY requires models/ to exist in build context (even if empty)
# Create empty directory first, then COPY (COPY will only copy if source exists)
RUN mkdir -p /tmp/models
COPY models /tmp/models/

RUN if [ "$INCLUDE_MODELS" = "true" ] && [ -d "/tmp/models" ] && [ "$(ls -A /tmp/models 2>/dev/null)" ]; then \
        echo "Copying models from local models/ directory..."; \
        mkdir -p /root/.cache/huggingface && \
        cp -r /tmp/models/* /root/.cache/huggingface/ && \
        echo "✅ Models copied from local directory"; \
        echo "Verifying model structure..."; \
        ls -la /root/.cache/huggingface/ || true; \
        find /root/.cache/huggingface -name "*.bin" -o -name "*.safetensors" -o -name "config.json" | head -5 || true; \
    elif [ "$DOWNLOAD_MODELS" = "true" ]; then \
        echo "Downloading models during build..."; \
        pip install --no-cache-dir huggingface-hub && \
        python -c "from huggingface_hub import snapshot_download, hf_hub_download; \
        import os, sys; \
        cache_dir = os.path.expanduser('~/.cache/huggingface'); \
        os.makedirs(cache_dir, exist_ok=True); \
        try: \
            # Check if models already exist before downloading \
            translation_model = os.path.join(cache_dir, 'hub', 'models--OpenNMT--nllb-200-3.3B-ct2-int8'); \
            lang_model = os.path.join(cache_dir, 'hub', 'models--facebook--fasttext-language-identification'); \
            if not os.path.exists(translation_model): \
                print('Downloading translation model...'); \
                snapshot_download('OpenNMT/nllb-200-3.3B-ct2-int8', cache_dir=cache_dir); \
            else: \
                print('✅ Translation model already exists'); \
            if not os.path.exists(lang_model): \
                print('Downloading language detection model...'); \
                hf_hub_download('facebook/fasttext-language-identification', 'model.bin', cache_dir=cache_dir); \
            else: \
                print('✅ Language detection model already exists'); \
        except Exception as e: \
            print(f'Warning: Model download failed: {e}', file=sys.stderr); \
            sys.exit(0)"; \
    else \
        echo "Skipping model download (models will be downloaded at runtime)"; \
        mkdir -p /root/.cache/huggingface; \
    fi

# Stage 3: Build Python dependencies
FROM python:${PYTHON_VERSION}-slim AS python-builder
ARG USE_CUDA=0

WORKDIR /build

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY language language/

# Install dependencies
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    UV_NO_DEV=1 \
    UV_LOCKED=1 \
    UV_NO_EDITABLE=1 \
    PYTHONOPTIMIZE=2 \
    RUSTFLAGS="-C target-cpu=native"

RUN uv sync --no-install-project ${USE_CUDA:+--extra cuda} && \
    uv sync ${USE_CUDA:+--extra cuda} && \
    find .venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find .venv -type f -name "*.pyc" -delete && \
    find .venv -type f -name "*.pyo" -delete && \
    rm -rf language

# Stage 4: Final runtime image
FROM python:${PYTHON_VERSION}-slim

ARG PYTHON_VERSION
ARG USE_CUDA=False

ENV HOME=/home/user \
    PATH=/home/user/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TRANSFORMERS_NO_ADVISORY_WARNINGS=1 \
    USE_CUDA=$USE_CUDA

# Create user
RUN useradd -m -u 1000 user && \
    mkdir -p $HOME/swagger-ui-assets && \
    chown -R user:user $HOME

USER user
WORKDIR $HOME

# Create cache directory for models (will be populated at runtime if not in image)
RUN mkdir -p /home/user/.cache/huggingface

# Copy models (if they were downloaded during build)
COPY --chown=user:user --from=model-builder /root/.cache/huggingface /home/user/.cache/huggingface

# Copy Python environment
COPY --chown=user:user --from=python-builder /build/.venv /home/user/.venv

# Copy Swagger UI assets
COPY --chown=user:user --from=swagger-ui /usr/share/nginx/html/swagger-ui.css $HOME/swagger-ui-assets/swagger-ui.css
COPY --chown=user:user --from=swagger-ui /usr/share/nginx/html/swagger-ui-bundle.js $HOME/swagger-ui-assets/swagger-ui-bundle.js

# Copy application code (only what's needed)
COPY --chown=user:user server/ server/
COPY --chown=user:user pyproject.toml ./

CMD ["nllb-api"]
