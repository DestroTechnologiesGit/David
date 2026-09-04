from fastapi import APIRouter

from server.api import health, language, translator

monitoring = APIRouter()
monitoring.include_router(health.router)

api_router = APIRouter()
api_router.include_router(language.router)
api_router.include_router(translator.router)
