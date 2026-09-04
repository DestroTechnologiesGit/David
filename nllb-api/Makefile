.PHONY: docker-build docker-push docker-build-cuda docker-build-cuda-offline docker-push-cuda docker-push-cuda-offline docker-run-cuda download-models help docker-clean

# Docker image configuration
IMAGE_NAME := pbusenius/nllb-api
OFFLINE_IMAGE_NAME := pbusenius/nllb-api
TAG ?= latest
VERSION ?= 0.2.0
DOCKERFILE := Dockerfile
DOCKERFILE_CUDA := Dockerfile.cuda

# Default target
help:
	@echo "Available targets:"
	@echo "  docker-build           - Build Docker image (CPU)"
	@echo "  docker-build-cuda     - Build Docker image (CUDA) without models"
	@echo "  docker-build-cuda-offline - Build Docker image (CUDA) with models"
	@echo "  docker-run-cuda       - Run CUDA Docker container with GPU support"
	@echo "  docker-push           - Push Docker image to registry"
	@echo "  docker-push-cuda      - Push CUDA Docker image to registry"
	@echo "  download-models       - Download models to local cache"
	@echo "  docker-clean          - Clean up Docker build cache and intermediate stages"
	@echo ""
	@echo "Variables:"
	@echo "  TAG                   - Image tag (default: latest)"
	@echo "  VERSION               - Version tag (default: 0.1)"
	@echo "  IMAGE_NAME            - Image name (default: pbusenius/nllb-api)"
	@echo "  OFFLINE_IMAGE_NAME    - Offline image name (default: pbusenius/offline-nllb-api)"
	@echo "  PORT                  - Server port (default: 49494)"

# Download models to local cache
download-models:
	@uv run python scripts/download_models.py

# Build Docker image (CPU)
docker-build:
	DOCKER_BUILDKIT=1 docker build --rm -f $(DOCKERFILE) -t $(IMAGE_NAME):$(TAG) -t $(IMAGE_NAME):$(VERSION) .

# Build Docker image (CUDA) without models
docker-build-cuda:
	@echo "Building CUDA image without models..."
	@if [ -d "models" ]; then \
		echo "Temporarily moving models directory..."; \
		mv models models.backup; \
	fi
	@mkdir -p models
	DOCKER_BUILDKIT=1 docker build --rm -f $(DOCKERFILE_CUDA) \
		--build-arg INCLUDE_MODELS=false \
		-t $(IMAGE_NAME):$(TAG) -t $(IMAGE_NAME):$(VERSION) .
	@rm -rf models
	@if [ -d "models.backup" ]; then \
		echo "Restoring models directory..."; \
		mv models.backup models; \
	fi

# Build Docker image (CUDA) with models (offline)
docker-build-cuda-offline:
	@echo "Building CUDA image with models (offline)..."
	@if [ ! -d "models" ]; then \
		echo "Error: models/ directory not found."; \
		echo "Run 'make download-models' first to download models."; \
		exit 1; \
	fi
	DOCKER_BUILDKIT=1 docker build --rm -f $(DOCKERFILE_CUDA) \
		--build-arg INCLUDE_MODELS=true \
		-t $(OFFLINE_IMAGE_NAME):$(TAG) -t $(OFFLINE_IMAGE_NAME):$(VERSION) .

# Run CUDA Docker container with GPU support
PORT ?= 49494
docker-run-cuda:
	docker run --init --rm --gpus all \
		-e USE_CUDA=True \
		-e SERVER_PORT=$(PORT) \
		-p $(PORT):$(PORT) \
		$(IMAGE_NAME):$(TAG)

# Push Docker image to registry
docker-push: docker-build
	docker push $(IMAGE_NAME):$(TAG)
	docker push $(IMAGE_NAME):$(VERSION)

# Push CUDA Docker image to registry
docker-push-cuda: docker-build-cuda
	docker push $(IMAGE_NAME):$(TAG)
	docker push $(IMAGE_NAME):$(VERSION)

# Push offline CUDA Docker image to registry
docker-push-cuda-offline: docker-build-cuda-offline
	docker push $(OFFLINE_IMAGE_NAME):$(TAG)
	docker push $(OFFLINE_IMAGE_NAME):$(VERSION)

# Clean up Docker build cache and intermediate stages
docker-clean:
	@echo "Cleaning build cache (this may take a moment)..."
	@docker builder prune -a -f
	@echo "Cleaning dangling images..."
	@docker image prune -f
	@echo "Done!"

