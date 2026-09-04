from uuid import uuid4

from pydantic_settings import BaseSettings


# Model size presets mapping to OpenNMT repositories
MODEL_SIZE_PRESETS = {
    "small": "OpenNMT/nllb-200-distilled-600M-ct2-int8",
    "medium": "OpenNMT/nllb-200-distilled-1.3B-ct2-int8",
    "large": "OpenNMT/nllb-200-3.3B-ct2-int8",
}


class Config(BaseSettings):
    """
    Summary
    -------
    the general config class

    Attributes
    ----------
    app_name (str)
        the name of the application

    server_port (int)
        the port to run the server on

    server_root_path (str)
        the root path for the server

    worker_count (int)
        the number of workers to use

    auth_token (str)
        the auth token to use for the server

    translator_repository (str)
        the repository to download the translator from

    translator_threads (int)
        the number of threads for the translator

    stub_translator (bool)
        whether to use a stub for the translator

    use_cuda (bool)
        whether to use CUDA for inference

    language_detector_repository (str)
        the repository to download the language detector from

    stub_language_detector (bool)
        whether to use a stub for the language detector

    access_control_allow_origin (str)
        the allowed origins for CORS

    access_control_allow_method_get (bool)
        whether to allow GET requests for CORS

    access_control_allow_method_post (bool)
        whether to allow POST requests for CORS

    access_control_allow_method_options (bool)
        whether to allow OPTIONS requests for CORS

    access_control_allow_method_delete (bool)
        whether to allow DELETE requests for CORS

    access_control_allow_method_put (bool)
        whether to allow PUT requests for CORS

    access_control_allow_method_patch (bool)
        whether to allow PATCH requests for CORS

    access_control_allow_method_head (bool)
        whether to allow HEAD requests for CORS

    access_control_allow_method_trace (bool)
        whether to allow TRACE requests for CORS

    access_control_allow_credentials (bool)
        whether to allow credentials for CORS

    access_control_allow_headers (str)
        the allowed headers for CORS

    access_control_expose_headers (str)
        the exposed headers for CORS

    access_control_max_age (int)
        the maximum age for CORS preflight requests

    otel_exporter_otlp_endpoint (str?)
        the endpoint for the OTLP exporter

    consul_auth_token (str?)
        the auth token for Consul

    consul_service_address (str?)
        the address of the Consul service

    consul_service_port (int)
        the port of the Consul service

    consul_service_scheme (str)
        the scheme for the Consul service (http or https)

    consul_service_token (str?)
        the token for the Consul service
    """

    app_name: str = "nllb-api"
    server_port: int = 49494
    server_root_path: str = "/api"
    worker_count: int = 1
    auth_token: str = str(uuid4())

    model_size: str | None = None  # Can be set to "small", "medium", or "large" via MODEL_SIZE env var
    translator_repository: str | None = None  # Can be explicitly set via TRANSLATOR_REPOSITORY env var (overrides MODEL_SIZE)
    translator_threads: int = 1
    stub_translator: bool = False
    testing: bool = False
    use_cuda: bool = False

    language_detector_repository: str = "facebook/fasttext-language-identification"
    stub_language_detector: bool = False

    access_control_allow_origin: str = "*"
    access_control_allow_method_get: bool = True
    access_control_allow_method_post: bool = True
    access_control_allow_method_options: bool = True
    access_control_allow_method_delete: bool = True
    access_control_allow_method_put: bool = True
    access_control_allow_method_patch: bool = True
    access_control_allow_method_head: bool = True
    access_control_allow_method_trace: bool = True
    access_control_allow_credentials: bool = True
    access_control_allow_headers: str = "*"
    access_control_expose_headers: str = "*"
    access_control_max_age: int = 600

    otel_enabled: bool = True
    otel_exporter_otlp_endpoint: str | None = None
    otel_prometheus_metrics_path: str = "/metrics"

    consul_http_addr: str | None = None
    consul_auth_token: str | None = None
    consul_service_address: str | None = None
    consul_service_port: int = 443
    consul_service_scheme: str = "https"

    def get_translator_repository(self) -> str:
        """
        Get the translator repository, resolving MODEL_SIZE if TRANSLATOR_REPOSITORY is not explicitly set.
        
        Priority:
        1. TRANSLATOR_REPOSITORY env var (if set)
        2. MODEL_SIZE preset (if MODEL_SIZE env var is set)
        3. Default to "large" (3.3B model)
        
        Returns
        -------
        str
            The translator repository to use
        """
        # If TRANSLATOR_REPOSITORY is explicitly set, use it (highest priority)
        if self.translator_repository:
            return self.translator_repository
        
        # If MODEL_SIZE is set, use the preset
        if self.model_size and self.model_size.lower() in MODEL_SIZE_PRESETS:
            return MODEL_SIZE_PRESETS[self.model_size.lower()]
        
        # Default fallback to large (3.3B)
        return MODEL_SIZE_PRESETS["large"]
