"""
Structured logging configuration using structlog.

structlog is the Python equivalent of Go's slog, providing:
- Structured logging with key-value pairs
- Context binding
- JSON output support
- Performance logging
- Integration with standard logging and OpenTelemetry
"""

import logging
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def add_app_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add application context to log events.

    Parameters
    ----------
    logger : logging.Logger
        The logger instance
    method_name : str
        The logging method name (info, error, etc.)
    event_dict : EventDict
        The event dictionary

    Returns
    -------
    EventDict
        The event dictionary with added context
    """
    # Add request ID if available from contextvars
    # This can be extended to add more context (user ID, trace ID, etc.)
    return event_dict


def setup_structlog(
    *,
    service_name: str,
    log_level: str = "INFO",
    use_json: bool = True,
    use_colors: bool = False,
) -> None:
    """
    Configure structlog for structured logging.

    Parameters
    ----------
    service_name : str
        Name of the service for log context
    log_level : str
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    use_json : bool
        Whether to output logs in JSON format
    use_colors : bool
        Whether to use colored output (only applies when not using JSON)
    """
    # Disable standard logging output - we only use structured logging
    # Set root logger to highest level and remove all handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.CRITICAL + 1)  # Disable all standard logging
    root_logger.handlers = []
    
    # Configure standard logging to use NullHandler (no output)
    # This is needed for structlog.stdlib integration but won't produce output
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=[logging.NullHandler()],  # No output from standard logging
        force=True,  # Override any existing configuration
    )
    
    # Silence uvicorn and other third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    logging.getLogger("fastapi").setLevel(logging.CRITICAL)
    
    # Build processors chain
    # Using PrintLoggerFactory, so we don't use stdlib-specific processors
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,  # Merge context variables
        structlog.processors.add_log_level,  # Add log level (generic, not stdlib)
        structlog.processors.TimeStamper(fmt="iso"),  # Add ISO timestamp
        structlog.processors.StackInfoRenderer(),  # Add stack info for exceptions
        structlog.processors.format_exc_info,  # Format exceptions
        add_app_context,  # Add custom app context
    ]

    # Add renderer based on output format
    if use_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=use_colors)
        )

    # Configure structlog with PrintLoggerFactory for direct output
    # This bypasses standard logging completely
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),  # Direct output, bypasses standard logging
        cache_logger_on_first_use=True,
    )

    # Set default context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None):
    """
    Get a structured logger instance.

    Parameters
    ----------
    name : str | None
        Logger name (defaults to calling module name)

    Returns
    -------
    structlog.BoundLogger
        Configured structured logger
    """
    return structlog.get_logger(name)


def bind_request_context(
    *,
    request_id: str | None = None,
    method: str | None = None,
    path: str | None = None,
    user_id: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Bind request context to structured logger.

    Parameters
    ----------
    request_id : str | None
        Unique request ID
    method : str | None
        HTTP method
    path : str | None
        Request path
    user_id : str | None
        User ID (if authenticated)
    **kwargs : Any
        Additional context to bind
    """
    context_vars: dict[str, Any] = {}
    if request_id:
        context_vars["request_id"] = request_id
    if method:
        context_vars["method"] = method
    if path:
        context_vars["path"] = path
    if user_id:
        context_vars["user_id"] = user_id
    context_vars.update(kwargs)
    structlog.contextvars.bind_contextvars(**context_vars)


def clear_request_context() -> None:
    """Clear request context from structured logger."""
    structlog.contextvars.clear_contextvars()

