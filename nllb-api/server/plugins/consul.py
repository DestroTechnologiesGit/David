from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiohttp import ClientSession
from fastapi import FastAPI


@asynccontextmanager
async def consul_register(
    app: FastAPI,
    *,
    app_name: str,
    app_id: str,
    consul_http_addr: str,
    consul_service_address: str,
    consul_service_port: int,
    consul_service_scheme: str,
    server_root_path: str,
    consul_auth_token: str | None = None,
) -> AsyncIterator[None]:
    """
    Summary
    -------
    a Consul service lifespan that registers the service on startup and deregisters it on shutdown

    Parameters
    ----------
    app (FastAPI)
        the application instance

    app_name (str)
        the name of the application

    app_id (str)
        the ID of the application instance

    consul_http_addr (str)
        the address of the Consul HTTP API (e.g. localhost:8500)

    consul_service_address (str)
        the address of the service to register with Consul

    consul_service_port (int)
        the port of the service to register with Consul

    consul_service_scheme (str)
        the scheme of the service to register with Consul (e.g. http or https)

    server_root_path (str)
        the root path of the server

    consul_auth_token (str?)
        an optional auth token for populating the `Authorization` header
    """
    headers: dict[str, str] = {}
    consul_server = f"https://{consul_http_addr}/v1/agent/service"

    health_endpoint = (
        f"{consul_service_scheme}://{consul_service_address}:{consul_service_port}"
        f"{server_root_path}/health"
    )

    health_check = {
        "HTTP": health_endpoint,
        "Interval": "10s",
        "Timeout": "5s",
    }

    payload = {
        "Name": app_name,
        "ID": app_id,
        "Tags": ["prometheus"],
        "Address": consul_service_address,
        "Port": consul_service_port,
        "Check": health_check,
        "Meta": {
            "metrics_port": f"{consul_service_port}",
            "metrics_path": "/metrics",
        },
    }

    if consul_auth_token:
        headers["Authorization"] = f"Bearer {consul_auth_token}"

    async with ClientSession(headers=headers) as session:
        async with session.put(
            f"{consul_server}/register",
            json=payload,
            params={"replace-existing-checks": "true"},
        ) as response:
            response.raise_for_status()

        try:
            yield

        finally:
            async with session.put(f"{consul_server}/deregister/{payload['ID']}"):
                pass
