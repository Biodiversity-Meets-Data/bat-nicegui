"""
BMD - Biodiversity Meets Data
Composition root for FastAPI + NiceGUI application.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from nicegui import app, ui

from api import register_api_routes
from config import SECRET_KEY
from database import init_db
from pages import register_ui_pages


@asynccontextmanager
async def lifespan(fastapi: FastAPI):
    _ = fastapi
    init_db()
    yield


fastapi_app = FastAPI(title="BMD API", lifespan=lifespan)

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
