import logging

import uvicorn

from server.app import app
from server.config import Config


def main() -> None:
    """
    Summary
    -------
    programmatically run the server with uvicorn
    """
    config = Config()
    
    # Create a custom log config that disables all uvicorn logging
    # This ensures only structured logging is used
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "",  # Empty format - no output
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.NullHandler",  # No output
            },
        },
        "loggers": {
            "uvicorn": {
                "handlers": ["default"],
                "level": "CRITICAL",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "CRITICAL",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["default"],
                "level": "CRITICAL",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["default"],
            "level": "CRITICAL",
        },
    }
    
    # Also silence uvicorn loggers directly
    logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.server_port,
        workers=config.worker_count,
        access_log=False,  # Disable uvicorn access logs - we use structured logging instead
        log_config=log_config,  # Use custom log config to suppress all uvicorn logs
    )


__all__ = ["app", "main"]
