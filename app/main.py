"""
BMD - Biodiversity Meets Data
Composition root for FastAPI + NiceGUI application.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import app, ui
from starlette.middleware.sessions import SessionMiddleware

from api import register_api_routes
from config import SECRET_KEY
from database import init_db
from pages import register_ui_pages


@asynccontextmanager
async def lifespan(fastapi: FastAPI) -> AsyncGenerator[None]:
    _ = fastapi
    init_db()
    yield


fastapi_app = FastAPI(
    title="BMD Biodiversity Analysis Tools (BATs) API", lifespan=lifespan
)

# Required by Authlib's OAuth client to stash state/nonce during the Keycloak
# login redirect round-trip. Separate cookie from NiceGUI's own storage_secret.
fastapi_app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Static files
app.add_static_files("/static", "static")

# Register routes/pages
register_api_routes(fastapi_app)
register_ui_pages()

# Mount NiceGUI to FastAPI
ui.run_with(
    fastapi_app,
    title="BMD - Biodiversity Meets Data",
    favicon="🌿",
    storage_secret=SECRET_KEY,
)
