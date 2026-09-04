from contextlib import asynccontextmanager
from logging import getLogger
from os import environ
from pathlib import Path
from random import choice
from string import ascii_letters, digits

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server.api import api_router, monitoring
from server.config import Config
from server.lifespans import load_language_detector, load_translator_model
from server.logging_config import setup_structlog, get_logger
from server.middleware.structured_logging import StructuredLoggingMiddleware
from server.plugins.consul import consul_register
from server.plugins.swagger_ui import setup_swagger_ui
from server.telemetry import get_log_handler, setup_telemetry


def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Summary
    -------
    the FastAPI exception handler

    Parameters
    ----------
    request (Request)
        the request

    exc (Exception)
        the exception

    Returns
    -------
    response (JSONResponse)
        the error response
    """
    logger = get_logger("nllb-api")
    # Log full exception details including traceback
    logger.error(
        "Unhandled exception",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        status_code=500,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
    )
    
    # Include exception details in response for debugging (can be disabled in production)
    import traceback
    error_detail = str(exc)
    if hasattr(exc, "__traceback__"):
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.error("Exception traceback", traceback=tb_str)
    
    return JSONResponse(
        content={
            "detail": "Internal Server Error",
            "error": error_detail,
            "error_type": type(exc).__name__,
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def extract_cors_values(string: str) -> list[str]:
    """
    Summary
    -------
    split a string by commas

    Parameters
    ----------
    string (str)
        the string to split

    Returns
    -------
    strings (list[str])
        the list of strings
    """
    return [stripped_chunk for chunk in string.split(",") if (stripped_chunk := chunk.strip())]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Summary
    -------
    lifespan context manager for FastAPI

    Parameters
    ----------
    app (FastAPI)
        the FastAPI application instance
    """
    config: Config = app.state.config
    app_id: str = app.state.app_id
    logger = get_logger("nllb-api")

    logger.info("Starting application", app_id=app_id, app_name=config.app_name)

    # Load models
    async with load_language_detector(
        config.language_detector_repository,
        stub=config.stub_language_detector,
    )(app):
        async with load_translator_model(
            config.get_translator_repository(),
            translator_threads=config.translator_threads,
            stub=config.stub_translator,
            testing=config.testing,
            use_cuda=config.use_cuda,
        )(app):
            # Register with Consul if configured
            if config.consul_http_addr and config.consul_service_address:
                logger.info("Registering with Consul", consul_addr=config.consul_http_addr)
                async with consul_register(
                    app,
                    app_name=config.app_name,
                    app_id=app_id,
                    consul_http_addr=config.consul_http_addr,
                    consul_service_address=config.consul_service_address,
                    consul_service_port=config.consul_service_port,
                    consul_service_scheme=config.consul_service_scheme,
                    server_root_path=config.server_root_path,
                    consul_auth_token=config.consul_auth_token,
                ):
                    logger.info("Application started successfully", app_id=app_id)
                    yield
            else:
                logger.info("Application started successfully", app_id=app_id)
                yield
    
    logger.info("Shutting down application", app_id=app_id)


def create_app(config: Config | None = None) -> FastAPI:
    """
    Summary
    -------
    create the FastAPI application
    """
    config = config or Config()
    ascii_letters_with_digits = f"{ascii_letters}{digits}"
    app_name = config.app_name
    app_id = f"{app_name}-{''.join(choice(ascii_letters_with_digits) for _ in range(4))}"  # noqa: S311
    
    # Set up structured logging
    log_level = environ.get("LOG_LEVEL", "INFO")
    use_json = environ.get("LOG_JSON", "true").lower() == "true"
    use_colors = environ.get("LOG_COLORS", "false").lower() == "true"
    setup_structlog(service_name=app_name, log_level=log_level, use_json=use_json, use_colors=use_colors)
    
    logger = get_logger(app_name)
    std_logger = getLogger(app_name)  # Keep for OpenTelemetry integration

    # Create FastAPI app
    fastapi_app = FastAPI(
        title=app_name,
        version="4.2.0",
        docs_url=f"{config.server_root_path}/schema/swagger",
        redoc_url=None,
        openapi_url=f"{config.server_root_path}/schema/openapi.json",
        openapi_tags=[
            {"name": "Monitoring"},
            {"name": "API"},
        ],
        lifespan=lifespan,
    )

    # Store config and app_id in app state
    fastapi_app.state.config = config
    fastapi_app.state.app_id = app_id

    # Set up OpenTelemetry
    if config.otel_enabled:
        # Set up logging handler if OTLP endpoint is configured
        # Note: OpenTelemetry handlers will still work but won't produce console output
        if config.otel_exporter_otlp_endpoint:
            handler = get_log_handler(otlp_service_name=app_name, otlp_service_instance_id=app_id)
            std_logger.addHandler(handler)
            # uvicorn.access logs will go to OTLP but not console
            uvicorn_logger = getLogger("uvicorn.access")
            uvicorn_logger.addHandler(handler)
            uvicorn_logger.propagate = False  # Prevent console output

        # Set up OpenTelemetry instrumentation
        setup_telemetry(fastapi_app, service_name=app_name)
        logger.info("OpenTelemetry instrumentation enabled", service_name=app_name, app_id=app_id)
    else:
        logger.info("OpenTelemetry instrumentation disabled")
    
    # Add structured logging middleware
    fastapi_app.add_middleware(StructuredLoggingMiddleware)

    # Configure CORS
    allow_methods_dict: dict[str, bool] = {
        "GET": config.access_control_allow_method_get,
        "POST": config.access_control_allow_method_post,
        "PUT": config.access_control_allow_method_put,
        "DELETE": config.access_control_allow_method_delete,
        "OPTIONS": config.access_control_allow_method_options,
        "PATCH": config.access_control_allow_method_patch,
        "HEAD": config.access_control_allow_method_head,
        "TRACE": config.access_control_allow_method_trace,
    }

    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=extract_cors_values(config.access_control_allow_origin),
        allow_methods=[method for method, is_allowed in allow_methods_dict.items() if is_allowed],
        allow_credentials=config.access_control_allow_credentials,
        allow_headers=extract_cors_values(config.access_control_allow_headers),
        expose_headers=extract_cors_values(config.access_control_expose_headers),
        max_age=config.access_control_max_age,
    )

    # Add exception handler
    fastapi_app.add_exception_handler(Exception, exception_handler)

    # Include routers
    fastapi_app.include_router(monitoring, prefix=config.server_root_path)
    fastapi_app.include_router(api_router, prefix=config.server_root_path, tags=["API"])

    # Configure static files for swagger-ui assets if they exist
    home_dir = Path(environ.get("HOME", str(Path.home())))
    swagger_ui_assets_path = home_dir / "swagger-ui-assets"
    if swagger_ui_assets_path.exists():
        fastapi_app.mount(
            f"{config.server_root_path}/swagger-ui-assets",
            StaticFiles(directory=str(swagger_ui_assets_path)),
            name="swagger-ui-assets",
        )
        setup_swagger_ui(fastapi_app, config.server_root_path)

    logger.info("Application created", app_name=app_name, app_id=app_id, version="4.2.0")
    
    return fastapi_app


# Create app instance for uvicorn
app = create_app()
