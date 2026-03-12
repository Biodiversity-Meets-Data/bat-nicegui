"""API router registration."""

from fastapi import FastAPI

from api.auth import router as auth_router
from api.workflows import router as workflows_router


def register_api_routes(fastapi_app: FastAPI) -> None:
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(workflows_router)
