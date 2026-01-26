"""
BMD - Biodiversity Meets Data
A NiceGUI + FastAPI application for biodiversity analysis workflows
"""

import os
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx
import jwt
from jinja2 import Environment, FileSystemLoader
from passlib.context import CryptContext
from nicegui import ui, app, Client

from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    update_user,
    delete_user,
    check_email_exists,
    create_workflow,
    get_user_workflows,
    update_workflow_status,
    get_workflow_by_id,
)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "bmd-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
WORKFLOW_API_URL = os.getenv(
    "WORKFLOW_API_URL", "http://workflow-api:8002/api/v1/workflows"
)
LOCAL_API_BASE_URL = os.getenv("LOCAL_API_BASE_URL", "http://localhost:8080")
WORKFLOW_API_KEY = os.getenv("WORKFLOW_API_KEY", "EpQaNpHS.EDed81RKaUno5Idj1AJgK2rLR7ieCb0h")
WORKFLOW_API_AUTH_HEADER = os.getenv("WORKFLOW_API_AUTH_HEADER", "Authorization")
WORKFLOW_API_AUTH_SCHEME = os.getenv("WORKFLOW_API_AUTH_SCHEME", "Bearer")
WORKFLOW_WEBHOOK_URL_TEMPLATE = os.getenv(
    "WORKFLOW_WEBHOOK_URL_TEMPLATE",
    "http://bmd-bat-app:8080/api/workflows/webhook/{workflow_id}",
)
WORKFLOW_DRY_RUN = os.getenv("WORKFLOW_DRY_RUN", "false").lower() == "true"
WORKFLOW_FORCE = os.getenv("WORKFLOW_FORCE", "false").lower() == "true"

# Static files
app.add_static_files("/static", "static")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_ENV = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)


def build_rocrate_zip(context: dict) -> bytes:
    #For dynamic templating in future with context variables
    #workflow_template = TEMPLATE_ENV.get_template("workflow.yaml")
    #rocrate_template = TEMPLATE_ENV.get_template("rocrate.json")
    #workflow_rendered = workflow_template.render(**context)
    #rocrate_rendered = rocrate_template.render(**context)

    template_dir = TEMPLATES_DIR / "terrestrial-sdm"
    workflow_rendered = (template_dir / "workflow.yaml").read_text(encoding="utf-8")
    rocrate_rendered = (template_dir / "ro-crate-metadata.json").read_text(encoding="utf-8")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workflow_path = temp_path / "workflow.yaml"
        rocrate_path = temp_path / "ro-crate-metadata.json"
        workflow_path.write_text(workflow_rendered, encoding="utf-8")
        rocrate_path.write_text(rocrate_rendered, encoding="utf-8")

        zip_path = temp_path / "rocrate.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(workflow_path, arcname="workflow.yaml")
            zip_file.write(rocrate_path, arcname="ro-crate-metadata.json")

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            contents = [f"{info.filename} ({info.file_size} bytes)" for info in zip_file.infolist()]
            print(f"RO-Crate contents: {contents}")

        return zip_path.read_bytes()


# Pydantic Models
class UserCreate(BaseModel):
    email: str
    password: str
    name: str


class UserLogin(BaseModel):
    email: str
    password: str


class WorkflowSubmit(BaseModel):
    name: str
    description: str
    species_name: str
    ecosystem_type: str
    geometry_type: str
    geometry_wkt: str
    parameters: dict


class WorkflowWebhook(BaseModel):
    workflow_id: str
    status: str
    results: Optional[dict] = None
    error_message: Optional[str] = None


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# Initialize database on startup
@asynccontextmanager
async def lifespan(fastapi: FastAPI):
    init_db()
    yield


# FastAPI app
fastapi_app = FastAPI(title="BMD API", lifespan=lifespan)


# API Endpoints
@fastapi_app.post("/api/auth/signup")
async def api_signup(user: UserCreate):
    existing = get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(user.password)
    user_id = create_user(user.email, hashed_pw, user.name)
    token = create_access_token(user_id)
    return {"access_token": token, "user_id": user_id}


@fastapi_app.post("/api/auth/login")
async def api_login(user: UserLogin):
    db_user = get_user_by_email(user.email)
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(db_user["user_id"])
    return {"access_token": token, "user_id": db_user["user_id"]}


@fastapi_app.post("/api/workflows/submit")
async def api_submit_workflow(
    workflow: WorkflowSubmit,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    parameters = workflow.parameters or {}
    time_period = parameters.get("time_period", "")
    directive_types = parameters.get("directive_types", [])
    if isinstance(directive_types, list):
        directive_types = ";".join([str(value) for value in directive_types])
    else:
        directive_types = str(directive_types)

    rocrate_context = {
        "workflow_name": workflow.name,
        "description": workflow.description or "",
        "species_name": workflow.species_name,
        "ecosystem_type": workflow.ecosystem_type,
        "geometry_type": workflow.geometry_type,
        "geometry_wkt": workflow.geometry_wkt,
        "time_period": time_period,
        "directive_types": directive_types,
    }

    rocrate_zip = build_rocrate_zip(rocrate_context)

    data = {}
    if WORKFLOW_WEBHOOK_URL_TEMPLATE:
        data["webhook_url"] = WORKFLOW_WEBHOOK_URL_TEMPLATE
    data["dry_run"] = str(WORKFLOW_DRY_RUN).lower()
    data["force"] = str(WORKFLOW_FORCE).lower()
    data["param-target_species"] = workflow.species_name
    data["param-climate_periods"] = time_period
    data["param-aoi_wkt"] = workflow.geometry_wkt
    
    """ params = {
        "param-target_species": workflow.species_name,
        "param-climate_periods": time_period,
        "param-aoi_wkt": workflow.geometry_wkt,
    } """

    headers = {}
    if WORKFLOW_API_KEY:
        if WORKFLOW_API_AUTH_SCHEME:
            headers[WORKFLOW_API_AUTH_HEADER] = (
                f"{WORKFLOW_API_AUTH_SCHEME} {WORKFLOW_API_KEY}"
            )
        else:
            headers[WORKFLOW_API_AUTH_HEADER] = WORKFLOW_API_KEY

    safe_headers = dict(headers)
    if WORKFLOW_API_AUTH_HEADER in safe_headers:
        safe_headers[WORKFLOW_API_AUTH_HEADER] = "***"
    print("Submitting workflow to API")
    print(f"URL: {WORKFLOW_API_URL}")
    print(f"Params: {params}")
    print(f"Data: {data}")
    print(f"Headers: {safe_headers}")
    print(f"RO-Crate bytes: {len(rocrate_zip)}")

    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.post(
                WORKFLOW_API_URL,
                #params=params,
                data=data,
                files={
                    "rocratefile": (
                        "rocrate.zip",
                        rocrate_zip,
                        "application/zip",
                    )
                },
                headers=headers,
            )
            print(f"Workflow API response: {response.status_code}")
            response_preview = response.text[:2000]
            print(f"Workflow API body: {response_preview}")
    except httpx.HTTPError as exc:
        print(f"Workflow API exception: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail=f"Workflow API error: {exc}") from exc

    if response.status_code >= 300:
        raise HTTPException(
            status_code=502,
            detail=f"Workflow API error: {response.status_code} {response.text}",
        )

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Workflow API returned invalid JSON") from exc

    workflow_id = response_payload.get("workflow_id") or response_payload.get("id")
    if not workflow_id:
        raise HTTPException(status_code=502, detail="Workflow API did not return workflow_id")

    # Print the workflow object
    print("=" * 60)
    print(f"WORKFLOW SUBMITTED - ID: {workflow_id}")
    print(f"User ID: {user_id}")
    print(f"Name: {workflow.name}")
    print(f"Description: {workflow.description}")
    print(f"Species Name: {workflow.species_name}")
    print(f"Ecosystem Type: {workflow.ecosystem_type}")
    print(f"Geometry Type: {workflow.geometry_type}")
    print(f"Geometry WKT: {workflow.geometry_wkt}")
    print(f"Parameters: {workflow.parameters}")
    print("=" * 60)

    # Create workflow in database
    create_workflow(
        workflow_id=workflow_id,
        user_id=user_id,
        name=workflow.name,
        description=workflow.description,
        species_name=workflow.species_name,
        ecosystem_type=workflow.ecosystem_type,
        geometry_type=workflow.geometry_type,
        geometry_wkt=workflow.geometry_wkt,
        parameters=str(workflow.parameters),
        status=response_payload.get("status", "submitted"),
    )

    return {
        "workflow_id": workflow_id,
        "status": response_payload.get("status", "submitted"),
    }


# TODO: Secure the webhook endpoint with a prefix token
@fastapi_app.post("/api/workflows/webhook/{workflow_id}")
async def workflow_webhook(workflow_id: str, webhook_data: WorkflowWebhook):
    """Webhook endpoint called by Argo Workflow when job completes"""
    print(f"WEBHOOK RECEIVED for workflow {workflow_id}")
    print(f"Status: {webhook_data.status}")
    
    # Remove results 
    print(f"Results: {webhook_data.results}")

    if webhook_data.status == "completed":
        update_workflow_status(
            workflow_id, "completed", results=str(webhook_data.results)
        )
    elif webhook_data.status == "failed":
        update_workflow_status(workflow_id, "failed", error=webhook_data.error_message)

    return {"status": "webhook processed"}


@fastapi_app.get("/api/workflows")
async def api_get_workflows(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    workflows = get_user_workflows(user_id)
    return {"workflows": workflows}


# --------------------------------------------------------------------------
# Permanent Workflow Deletion Endpoint
# --------------------------------------------------------------------------
@fastapi_app.delete("/api/workflows/{workflow_id}")
async def api_delete_workflow(
    workflow_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = verify_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Workflow not found")

    # permanent delete
    from database import delete_workflow

    delete_workflow(workflow_id)

    return {"status": "deleted", "workflow_id": workflow_id}


# ============================================================================
# NiceGUI UI Components
# ============================================================================


def create_footer():
    """Global BMD footer"""
    with ui.footer().classes(
        "w-full justify-center items-center py-3 bg-transparent text-xs text-gray-500",
    ):
        ui.html(
            """
            <span>
                © <a href="https://bmd-project.eu" target="_blank" class="font-medium text-emerald-700 hover:underline">BMD</a> 2025.
                Built with 💚 at
                <a href="https://www.ufz.de" target="_blank" class="font-medium text-emerald-700 hover:underline">Helmholtz‑UFZ</a>
                for biodiversity research.
            </span>
            """,
            sanitize=False,
        )


def apply_bmd_theme():
    """Apply BMD theme styling"""
    ui.add_head_html(
        """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet-draw@1.0.4/dist/leaflet.draw.js"></script>
    <style>
        :root {
            --bmd-green: #2ECC71;
            --bmd-dark-green: #1A9F53;
            --bmd-teal: #17A2B8;
            --bmd-blue: #0077B6;
            --bmd-bg: #F0F9F4;
            --bmd-text: #1A3A2A;
        }

        body {
            font-family: 'Outfit', sans-serif !important;
            min-height: 100vh;
            background: #F0F9F4; /* default for app/dashboard */
        }

        /* ------------------------------------------------------------------
           Public pages (login / signup only)
           ------------------------------------------------------------------ */
        body.public-auth {
            background-image:
                url("https://www.transparenttextures.com/patterns/leaves.png"),
                radial-gradient(circle at 25% 30%, rgba(46,204,113,0.35), transparent 45%),
                radial-gradient(circle at 75% 70%, rgba(23,162,184,0.35), transparent 45%),
                linear-gradient(135deg, #EAF6F0 0%, #DDEFE5 50%, #CFE8E3 100%);
            background-size: 180px 180px, auto, auto, cover;
            background-repeat: repeat;
            background-attachment: fixed;
        }

        .bmd-header {
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 50%, #0077B6 100%);
            padding: 1rem 2rem;
            box-shadow: 0 4px 20px rgba(46, 204, 113, 0.3);
        }

        .bmd-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(26, 58, 42, 0.1);
            border: 1px solid rgba(46, 204, 113, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .bmd-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(46, 204, 113, 0.15);
        }

        .bmd-btn {
            background: linear-gradient(135deg, #2ECC71 0%, #1A9F53 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 12px 24px;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(46, 204, 113, 0.3);
        }

        .bmd-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 204, 113, 0.4);
        }

        .bmd-btn-secondary {
            background: linear-gradient(135deg, #17A2B8 0%, #0077B6 100%);
        }

        .bmd-btn-danger {
            background: linear-gradient(135deg, #E74C3C 0%, #C0392B 100%);
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
        }

        .bmd-btn-danger:hover {
            box-shadow: 0 6px 20px rgba(231, 76, 60, 0.4);
        }

        .bmd-logo-text {
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            font-size: 1.8rem;
            background: linear-gradient(135deg, #ffffff 0%, #E8F5E9 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .bmd-subtitle {
            font-family: 'Space Mono', monospace;
            font-size: 0.85rem;
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 0.5px;
        }

        #map {
            height: 400px;
            width: 100%;
            border-radius: 12px;
            border: 2px solid rgba(46, 204, 113, 0.2);
        }

        .leaflet-draw-toolbar a {
            background-color: #2ECC71 !important;
        }

        .nav-link {
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .nav-link:hover {
            background: rgba(255, 255, 255, 0.15);
            color: white;
        }

        .nav-link.active {
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }

        .required-asterisk {
            color: #E74C3C;
            margin-left: 2px;
        }

        .field-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: #374151;
            margin-bottom: 4px;
        }

        .optional-hint {
            font-size: 0.75rem;
            color: #9CA3AF;
            font-weight: 400;
        }

        /* Ecosystem selection cards */
        .ecosystem-card {
            background: white;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(26, 58, 42, 0.1);
            border: 2px solid rgba(46, 204, 113, 0.2);
            transition: all 0.4s ease;
            cursor: pointer;
        }

        .ecosystem-card:not(.disabled):hover {
            transform: translateY(-8px);
            box-shadow: 0 16px 48px rgba(46, 204, 113, 0.25);
            background: linear-gradient(135deg, rgba(46, 204, 113, 0.05) 0%, rgba(23, 162, 184, 0.05) 100%);
            border-color: rgba(46, 204, 113, 0.4);
        }

        .ecosystem-card.disabled {
            opacity: 0.5;
            cursor: not-allowed;
            background: #f5f5f5;
        }

        .ecosystem-icon {
            font-size: 6rem;
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .ecosystem-card.disabled .ecosystem-icon {
            background: #9CA3AF;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .ecosystem-action-btn {
            padding: 8px 16px;
            min-height: 38px;
            font-size: 0.875rem;
        }

        .species-pill {
            display: inline-block;
            margin-left: 6px;
            padding: 2px 8px;
            border-radius: 999px;
            background: rgba(46, 204, 113, 0.15);
            color: #1A9F53;
            font-size: 0.7rem;
            font-weight: 600;
            vertical-align: middle;
        }

        .time-period-slider .q-slider__marker-label {
            font-size: 0.7rem;
            max-width: 70px;
            white-space: normal;
            line-height: 1.1;
            text-align: center;
        }
    </style>
    """
    )


def required_label(text: str) -> None:
    """Create a label with required asterisk"""
    with ui.row().classes("items-center gap-0 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("*").classes("required-asterisk")


def optional_label(text: str) -> None:
    """Create a label with optional hint"""
    with ui.row().classes("items-center gap-2 mb-1"):
        ui.label(text).classes("field-label")
        ui.label("(optional)").classes("optional-hint")


def create_header(current_page: str = ""):
    """Create the BMD header with navigation"""
    user_name = app.storage.user.get("user_name", "User")

    with ui.header().classes("bmd-header items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            #ui.image("/static/logo.png").classes(
            #    "w-12 h-12 object-contain cursor-pointer"
            #).on("click", lambda: ui.navigate.to("/workflows"))
            with ui.column().classes("gap-0 cursor-pointer").on(
                "click", lambda: ui.navigate.to("/workflows")
            ):
                ui.label("BMD").classes("bmd-logo-text")
                ui.label("Biodiversity Meets Data").classes("bmd-subtitle")

        with ui.row().classes("gap-3 items-center"):
            ui.link("Workflows", "/workflows").classes(
                f'nav-link {"active" if current_page == "workflows" else ""}'
            )
            ui.button(
                "+ New Workflow", on_click=lambda: ui.navigate.to("/select-workflow")
            ).props("unelevated rounded color=white text-color=primary").classes(
                "font-semibold"
            )

            # User dropdown menu
            with ui.button(icon="account_circle").props("flat round color=white"):
                with ui.menu().classes("min-w-48"):
                    with ui.row().classes("px-4 py-3 border-b border-gray-100"):
                        with ui.column().classes("gap-0"):
                            ui.label(user_name).classes("font-semibold text-gray-800")
                            ui.label("Logged in").classes("text-xs text-gray-500")
                    ui.menu_item(
                        "Account Settings", on_click=lambda: ui.navigate.to("/account")
                    ).classes("py-2")
                    ui.separator()
                    ui.menu_item("Logout", on_click=lambda: do_logout()).classes(
                        "py-2 text-red-600"
                    )


async def do_logout():
    app.storage.user.clear()
    ui.navigate.to("/login")


def check_auth() -> Optional[str]:
    """Check if user is authenticated"""
    token = app.storage.user.get("token")
    if not token:
        return None
    user_id = verify_token(token)
    return user_id


# ============================================================================
# Login Page
# ============================================================================
@ui.page("/login")
def login_page():
    apply_bmd_theme()
    ui.run_javascript("document.body.classList.add('public-auth')")

    async def do_login():
        email = email_input.value
        password = password_input.value

        if not email or not password:
            ui.notify("Please fill in all fields", type="negative")
            return

        user = get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            ui.notify("Invalid email or password", type="negative")
            return

        token = create_access_token(user["user_id"])
        app.storage.user["token"] = token
        app.storage.user["user_id"] = user["user_id"]
        app.storage.user["user_name"] = user["name"]
        ui.navigate.to("/workflows")

    with ui.column().classes("w-full min-h-screen items-center p-8 overflow-visible"):
        # Brand header (NOT vertically centered)
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

        # Centered card
        with ui.column().classes("w-full items-center"):
            with ui.card().classes("bmd-card p-8 w-full max-w-md"):
                ui.label("Welcome Back").classes(
                    "text-2xl font-semibold text-gray-800 mb-4"
                )

                with ui.column().classes("w-full gap-1"):
                    required_label("Email")
                    email_input = (
                        ui.input(placeholder="your@email.com")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Password")
                    password_input = (
                        ui.input(placeholder="Enter password", password=True)
                        .props("outlined")
                        .classes("w-full")
                    )
                password_input.on("keydown.enter", do_login)

                ui.button("Sign In", on_click=do_login).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                )

                with ui.row().classes("w-full justify-center mt-4 gap-1"):
                    ui.label("Don't have an account?").classes("text-gray-500")
                    ui.link("Sign up", "/signup").classes("text-teal-600 font-semibold")
    create_footer()


# ============================================================================
# Signup Page
# ============================================================================
@ui.page("/signup")
def signup_page():
    apply_bmd_theme()
    ui.run_javascript("document.body.classList.add('public-auth')")

    async def do_signup():
        name = name_input.value
        email = email_input.value
        password = password_input.value
        confirm = confirm_input.value
        orcid = orcid_input.value.strip() if orcid_input.value else None

        if not all([name, email, password, confirm]):
            ui.notify("Please fill in all required fields", type="negative")
            return

        if password != confirm:
            ui.notify("Passwords do not match", type="negative")
            return

        if len(password) < 6:
            ui.notify("Password must be at least 6 characters", type="negative")
            return

        # Validate ORCID format if provided
        if orcid:
            import re

            orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
            if not re.match(orcid_pattern, orcid):
                ui.notify(
                    "Invalid ORCID format. Use: 0000-0000-0000-0000", type="negative"
                )
                return

        existing = get_user_by_email(email)
        if existing:
            ui.notify("Email already registered", type="negative")
            return

        hashed_pw = hash_password(password)
        user_id = create_user(email, hashed_pw, name, orcid=orcid)
        token = create_access_token(user_id)

        app.storage.user["token"] = token
        app.storage.user["user_id"] = user_id
        app.storage.user["user_name"] = name
        ui.navigate.to("/workflows")

    with ui.column().classes("w-full min-h-screen items-center p-8 overflow-visible"):
        # Brand header (NOT vertically centered)
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

        # Centered card
        with ui.column().classes("w-full items-center"):
            with ui.card().classes("bmd-card p-8 w-full max-w-md"):
                ui.label("Create Account").classes(
                    "text-2xl font-semibold text-gray-800 mb-4"
                )

                with ui.column().classes("w-full gap-1"):
                    required_label("Full Name")
                    name_input = (
                        ui.input(placeholder="John Doe")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Email")
                    email_input = (
                        ui.input(placeholder="your@email.com")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    optional_label("ORCID")
                    orcid_input = (
                        ui.input(placeholder="0000-0000-0000-0000")
                        .props("outlined")
                        .classes("w-full")
                    )
                    ui.label("Your ORCID identifier for research attribution").classes(
                        "text-xs text-gray-400 mt-1"
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Password")
                    password_input = (
                        ui.input(placeholder="At least 6 characters", password=True)
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Confirm Password")
                    confirm_input = (
                        ui.input(placeholder="Repeat password", password=True)
                        .props("outlined")
                        .classes("w-full")
                    )
                confirm_input.on("keydown.enter", do_signup)

                ui.button("Create Account", on_click=do_signup).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                )

                with ui.row().classes("w-full justify-center mt-4 gap-1"):
                    ui.label("Already have an account?").classes("text-gray-500")
                    ui.link("Sign in", "/login").classes("text-teal-600 font-semibold")
    create_footer()


# ============================================================================
# Select Workflow Page (NEW)
# ============================================================================
@ui.page("/select-workflow")
async def select_workflow_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header()

    # Markdown content for ecosystems
    terrestrial_about_md = """
## Terrestrial Ecosystems

Analyze biodiversity patterns across land-based ecosystems including forests, grasslands, mountains, and urban areas.

### Features:
- **Species Distribution Modeling** - Predict suitable habitats for terrestrial species
- **Multi-scale Analysis** - From local to continental scales
- **Environmental Variables** - Temperature, precipitation, elevation, soil types
- **Temporal Analysis** - Historical and current data integration

### Typical Use Cases:
- Forest biodiversity assessments
- Conservation planning for protected areas
- Climate change impact studies
- Species range predictions
"""

    freshwater_about_md = """
## Freshwater Ecosystems

Analyze biodiversity in rivers, lakes, wetlands, and other freshwater habitats.

### Features:
- **Aquatic Species Modeling** - Fish, amphibians, invertebrates
- **Hydrological Integration** - Water quality, flow patterns
- **Habitat Connectivity** - River network analysis
- **Invasive Species Tracking** - Monitor non-native species spread

### Status:
🚧 **Coming Soon** - This workflow is currently under development and will be available in a future release.
"""

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
        ui.label("Select Workflow Type").classes("text-3xl font-bold mb-2").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )
        ui.label("Choose the ecosystem type for your biodiversity analysis").classes(
            "text-lg text-gray-600 mb-6"
        )

        with ui.row().classes("w-full gap-8 flex-wrap lg:flex-nowrap"):
            # Terrestrial Card
            with ui.card().classes("ecosystem-card p-8 flex-1 min-w-80"):
                with ui.column().classes("w-full items-center gap-4"):
                    ui.icon("forest").classes("ecosystem-icon")
                    ui.label("Terrestrial").classes("text-2xl font-bold text-gray-800")
                    ui.label(
                        "Land-based ecosystems: forests, grasslands, mountains"
                    ).classes("text-sm text-gray-600 text-center")

                    with ui.row().classes("w-full gap-3 mt-6"):

                        async def show_terrestrial_about():
                            with ui.dialog() as dialog, ui.card().classes(
                                "p-6 max-w-2xl"
                            ):
                                ui.markdown(terrestrial_about_md)
                                ui.button("Close", on_click=dialog.close).classes(
                                    "bmd-btn mt-4"
                                )
                            dialog.open()

                        ui.button(
                            "About",
                            on_click=show_terrestrial_about,
                        ).props(
                            "outline"
                        ).classes("ecosystem-action-btn flex-1").style(
                            "background: rgba(46, 204, 113, 0.05); "
                            "border: 2px solid rgba(46, 204, 113, 0.3); "
                            "color: #1A9F53;"
                        )

                        ui.button(
                            "Select",
                            on_click=lambda: ui.navigate.to("/create/terrestrial"),
                        ).classes("bmd-btn ecosystem-action-btn flex-1").props(
                            "icon=arrow_forward"
                        )

            # Freshwater Card (Disabled)
            with ui.card().classes("ecosystem-card disabled p-8 flex-1 min-w-80"):
                with ui.column().classes("w-full items-center gap-4"):
                    ui.icon("water").classes("ecosystem-icon")
                    ui.label("Freshwater").classes("text-2xl font-bold text-gray-500")
                    ui.label("Rivers, lakes, wetlands, and aquatic habitats").classes(
                        "text-sm text-gray-500 text-center"
                    )
                    ui.badge("COMING SOON").props("color=grey").classes("mt-2")

                    with ui.row().classes("w-full gap-3 mt-6"):

                        async def show_freshwater_about():
                            with ui.dialog() as dialog, ui.card().classes(
                                "p-6 max-w-2xl"
                            ):
                                ui.markdown(freshwater_about_md)
                                ui.button("Close", on_click=dialog.close).classes(
                                    "bmd-btn mt-4"
                                )
                            dialog.open()

                        ui.button(
                            "About",
                            on_click=show_freshwater_about,
                        ).props(
                            "outline"
                        ).classes("ecosystem-action-btn flex-1").style(
                            "background: rgba(156, 163, 175, 0.05); "
                            "border: 2px solid rgba(156, 163, 175, 0.3); "
                            "color: #6B7280;"
                        )

                        ui.button(
                            "Select",
                        ).classes("ecosystem-action-btn flex-1").props(
                            "disable"
                        ).style("background: #E5E7EB; color: #9CA3AF;")

    create_footer()


# ============================================================================
# Signup Page
# ============================================================================
@ui.page("/signup")
def signup_page():
    apply_bmd_theme()
    ui.run_javascript("document.body.classList.add('public-auth')")

    async def do_signup():
        name = name_input.value
        email = email_input.value
        password = password_input.value
        confirm = confirm_input.value
        orcid = orcid_input.value.strip() if orcid_input.value else None

        if not all([name, email, password, confirm]):
            ui.notify("Please fill in all required fields", type="negative")
            return

        if password != confirm:
            ui.notify("Passwords do not match", type="negative")
            return

        if len(password) < 6:
            ui.notify("Password must be at least 6 characters", type="negative")
            return

        # Validate ORCID format if provided
        if orcid:
            import re

            orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
            if not re.match(orcid_pattern, orcid):
                ui.notify(
                    "Invalid ORCID format. Use: 0000-0000-0000-0000", type="negative"
                )
                return

        existing = get_user_by_email(email)
        if existing:
            ui.notify("Email already registered", type="negative")
            return

        hashed_pw = hash_password(password)
        user_id = create_user(email, hashed_pw, name, orcid=orcid)
        token = create_access_token(user_id)

        app.storage.user["token"] = token
        app.storage.user["user_id"] = user_id
        app.storage.user["user_name"] = name
        ui.navigate.to("/workflows")

    with ui.column().classes("w-full min-h-screen items-center p-8 overflow-visible"):
        # Brand header (NOT vertically centered)
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

        # Centered card
        with ui.column().classes("w-full items-center"):
            with ui.card().classes("bmd-card p-8 w-full max-w-md"):
                ui.label("Create Account").classes(
                    "text-2xl font-semibold text-gray-800 mb-4"
                )

                with ui.column().classes("w-full gap-1"):
                    required_label("Full Name")
                    name_input = (
                        ui.input(placeholder="John Doe")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Email")
                    email_input = (
                        ui.input(placeholder="your@email.com")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    optional_label("ORCID")
                    orcid_input = (
                        ui.input(placeholder="0000-0000-0000-0000")
                        .props("outlined")
                        .classes("w-full")
                    )
                    ui.label("Your ORCID identifier for research attribution").classes(
                        "text-xs text-gray-400 mt-1"
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Password")
                    password_input = (
                        ui.input(placeholder="At least 6 characters", password=True)
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-3"):
                    required_label("Confirm Password")
                    confirm_input = (
                        ui.input(placeholder="Repeat password", password=True)
                        .props("outlined")
                        .classes("w-full")
                    )
                confirm_input.on("keydown.enter", do_signup)

                ui.button("Create Account", on_click=do_signup).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                )

                with ui.row().classes("w-full justify-center mt-4 gap-1"):
                    ui.label("Already have an account?").classes("text-gray-500")
                    ui.link("Sign in", "/login").classes("text-teal-600 font-semibold")
    create_footer()


# ============================================================================
# Account Page
# ============================================================================
@ui.page("/account")
async def account_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("account")

    user = get_user_by_id(user_id)
    if not user:
        ui.label("User not found").classes("text-xl text-red-500")
        create_footer()
        return

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        ui.label("Account Settings").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

        # Profile Card
        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Profile Information").classes(
                "text-xl font-semibold text-gray-800 mb-4"
            )

            with ui.column().classes("w-full gap-1"):
                required_label("Full Name")
                name_input = (
                    ui.input(value=user.get("name", ""))
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("Email")
                email_input = (
                    ui.input(value=user.get("email", ""))
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                optional_label("ORCID")
                orcid_input = (
                    ui.input(value=user.get("orcid", "") or "")
                    .props("outlined")
                    .classes("w-full")
                )
                ui.label("Your ORCID identifier (format: 0000-0000-0000-0000)").classes(
                    "text-xs text-gray-400 mt-1"
                )

            async def save_profile():
                name = name_input.value.strip()
                email = email_input.value.strip()
                orcid = orcid_input.value.strip() if orcid_input.value else None

                if not name or not email:
                    ui.notify("Name and email are required", type="negative")
                    return

                # Check if email is taken by another user
                if check_email_exists(email, exclude_user_id=user_id):
                    ui.notify("Email is already in use", type="negative")
                    return

                # Validate ORCID format if provided
                if orcid:
                    import re

                    orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                    if not re.match(orcid_pattern, orcid):
                        ui.notify("Invalid ORCID format", type="negative")
                        return

                update_user(
                    user_id, name=name, email=email, orcid=orcid if orcid else ""
                )
                app.storage.user["user_name"] = name
                ui.notify("Profile updated successfully", type="positive")

            ui.button("Save Changes", on_click=save_profile).classes("bmd-btn mt-6")

        # Password Card
        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Change Password").classes(
                "text-xl font-semibold text-gray-800 mb-4"
            )

            with ui.column().classes("w-full gap-1"):
                required_label("Current Password")
                current_pw_input = (
                    ui.input(placeholder="Enter current password", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("New Password")
                new_pw_input = (
                    ui.input(placeholder="At least 6 characters", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            with ui.column().classes("w-full gap-1 mt-4"):
                required_label("Confirm New Password")
                confirm_pw_input = (
                    ui.input(placeholder="Repeat new password", password=True)
                    .props("outlined")
                    .classes("w-full")
                )

            async def change_password():
                current_pw = current_pw_input.value
                new_pw = new_pw_input.value
                confirm_pw = confirm_pw_input.value

                if not all([current_pw, new_pw, confirm_pw]):
                    ui.notify("Please fill in all password fields", type="negative")
                    return

                # Verify current password
                if not verify_password(current_pw, user["password_hash"]):
                    ui.notify("Current password is incorrect", type="negative")
                    return

                if new_pw != confirm_pw:
                    ui.notify("New passwords do not match", type="negative")
                    return

                if len(new_pw) < 6:
                    ui.notify("Password must be at least 6 characters", type="negative")
                    return

                new_hash = hash_password(new_pw)
                update_user(user_id, password_hash=new_hash)

                # Clear input fields
                current_pw_input.value = ""
                new_pw_input.value = ""
                confirm_pw_input.value = ""

                ui.notify("Password changed successfully", type="positive")

            ui.button("Change Password", on_click=change_password).classes(
                "bmd-btn-secondary bmd-btn mt-6"
            )

        # Danger Zone Card
        with ui.card().classes("bmd-card p-6 w-full border-2 border-red-200"):
            ui.label("Danger Zone").classes("text-xl font-semibold text-red-600 mb-2")
            ui.label(
                "Once you delete your account, there is no going back. All your workflows will be permanently deleted."
            ).classes("text-sm text-gray-600 mb-4")

            async def confirm_delete():
                with ui.dialog() as dialog, ui.card().classes("p-6"):
                    ui.label("Delete Account").classes(
                        "text-xl font-bold text-red-600 mb-4"
                    )
                    ui.label(
                        "Are you sure you want to delete your account? This action cannot be undone."
                    ).classes("text-gray-600 mb-4")

                    with ui.column().classes("w-full gap-1 mb-4"):
                        ui.label("Type your email to confirm:").classes(
                            "text-sm font-medium"
                        )
                        confirm_email_input = (
                            ui.input(placeholder=user["email"])
                            .props("outlined")
                            .classes("w-full")
                        )

                    with ui.row().classes("gap-4 justify-end"):
                        ui.button("Cancel", on_click=dialog.close).props("flat")

                        async def do_delete():
                            if confirm_email_input.value != user["email"]:
                                ui.notify("Email doesn't match", type="negative")
                                return

                            delete_user(user_id)
                            app.storage.user.clear()
                            dialog.close()
                            ui.notify("Account deleted", type="info")
                            ui.navigate.to("/login")

                        ui.button("Delete Account", on_click=do_delete).classes(
                            "bmd-btn-danger bmd-btn"
                        )

                dialog.open()

            ui.button("Delete Account", on_click=confirm_delete).classes(
                "bmd-btn-danger bmd-btn"
            ).props("icon=delete")
    create_footer()


# ============================================================================
# Create Workflow Page
# ============================================================================
@ui.page("/create/terrestrial")
async def create_page(client: Client):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    time_periods = [
        "1981-2010",
        "2011-2040",
        "2041-2070",
        "2071-2100"
    ]
    import json
    from pathlib import Path

    static_candidates = [
        Path(__file__).resolve().parent / "static",
        Path(__file__).resolve().parent.parent / "static",
    ]
    static_dir = next((p for p in static_candidates if p.exists()), static_candidates[0])
    ias_path = static_dir / "eu-ias-directive.json"
    try:
        with ias_path.open("r", encoding="utf-8") as handle:
            ias_data = json.load(handle)
    except Exception:
        ias_data = []

    ias_species_names = [
        entry.get("scientificName", "").strip()
        for entry in ias_data
        if entry.get("scientificName")
    ]
    habitat_species_names = []
    species_directive_map = {name: "IAS" for name in ias_species_names}

    def build_species_options(selected_directives):
        options = {}
        if "invasive_species" in (selected_directives or []):
            for name in ias_species_names:
                options[name] = f"{name} <span class='species-pill'>IAS</span>"
        if "habitat" in (selected_directives or []):
            for name in habitat_species_names:
                options[name] = f"{name} <span class='species-pill'>HAB</span>"
        return options

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("create")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        ui.label("Create New Workflow").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

        with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
            # Form Section
            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                ui.label("Workflow Parameters").classes(
                    "text-xl font-semibold mb-4 text-gray-800"
                )

                with ui.column().classes("w-full gap-1"):
                    required_label("Workflow Name")
                    name_input = (
                        ui.input(placeholder="e.g., Alpine Species Survey")
                        .props("outlined")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-4"):
                    optional_label("Description")
                    desc_input = (
                        ui.textarea(placeholder="Describe your analysis...")
                        .props("outlined rows=3")
                        .classes("w-full")
                    )

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Choose EU Directive")
                    with ui.row().classes("w-full gap-4"):
                        invasive_cb = ui.checkbox(
                            "Invasive Species", value=False
                        ).props("checked-icon=check_box").classes("flex-1")
                        habitat_cb = (
                            ui.checkbox("Habitat", value=False)
                            .props("checked-icon=check_box disable")
                            .classes("flex-1")
                        )

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Species List")
                    species_select = (
                        ui.select(
                            options=build_species_options([]),
                            value=None,
                        )
                        .props("outlined use-input input-debounce=0 options-html")
                        .classes("w-full")
                    )

                def update_species_options():
                    selected = []
                    if invasive_cb.value:
                        selected.append("invasive_species")
                    if habitat_cb.value:
                        selected.append("habitat")
                    species_select.options = build_species_options(selected)
                    if species_select.value not in species_select.options:
                        species_select.value = None
                    species_select.update()

                def update_species_display():
                    species_select.props(
                        f"display-value={json.dumps(species_select.value or '')}"
                    )
                    species_select.update()

                invasive_cb.on_value_change(lambda _: update_species_options())
                habitat_cb.on_value_change(lambda _: update_species_options())
                species_select.on_value_change(lambda _: update_species_display())

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Time Period")
                    time_period_checks = []
                    for period in time_periods:
                        time_period_checks.append(
                            ui.checkbox(period, value=False).classes("w-full")
                        )

                def get_selected_time_periods():
                    return [
                        period
                        for period, checkbox in zip(time_periods, time_period_checks)
                        if checkbox.value
                    ]


                ui.label("Additional Parameters").classes(
                    "text-sm font-semibold text-gray-600 mt-4 mb-2"
                )

                with ui.row().classes("w-full gap-4 mb-4"):
                    min_obs = (
                        ui.number("Min Observations", value=10)
                        .props("outlined")
                        .classes("flex-1")
                    )
                    confidence = ui.slider(min=0, max=100, value=80).classes("flex-1")
                    ui.label().bind_text_from(
                        confidence, "value", lambda v: f"Confidence: {v}%"
                    )

                include_historical = ui.checkbox("Include historical data", value=True)
                generate_report = ui.checkbox("Generate PDF report", value=True)

                with ui.column().classes("w-full gap-1 mt-4"):
                    required_label("Selected Area")
                    geometry_label = ui.label("WKT: None - Draw on map →").classes(
                        "text-sm text-gray-500 p-3 bg-gray-50 rounded-lg"
                    ).props("id=geometry-wkt")

                async def submit_workflow():
                    if not name_input.value:
                        ui.notify("Please enter a workflow name", type="warning")
                        return
                    directive_values = []
                    if invasive_cb.value:
                        directive_values.append("invasive_species")
                    if habitat_cb.value:
                        directive_values.append("habitat")

                    if not directive_values:
                        ui.notify("Please choose an EU directive", type="warning")
                        return
                    if not species_select.value:
                        ui.notify("Please select a species", type="warning")
                        return
                    selected_time_periods = get_selected_time_periods()
                    if not selected_time_periods:
                        ui.notify("Please select a time period", type="warning")
                        return

                    # Get geometry data directly from JavaScript, defensive and with longer timeout
                    geo_type = await ui.run_javascript(
                        "return (window.geometryType ? window.geometryType : null);",
                        timeout=5.0,
                    )
                    geo_wkt = await ui.run_javascript(
                        "return (window.geometryWkt ? window.geometryWkt : null);",
                        timeout=5.0,
                    )

                    if not geo_type or geo_type == "null":
                        ui.notify("Please draw an area on the map", type="warning")
                        return
                    if not geo_wkt or geo_wkt == "null":
                        ui.notify("Geometry WKT not available", type="warning")
                        return

                    token = app.storage.user.get("token")

                    workflow_payload = {
                        "name": name_input.value,
                        "description": desc_input.value or "",
                        "species_name": species_select.value,
                        "ecosystem_type": "terrestrial",
                        "geometry_type": geo_type,
                        "geometry_wkt": geo_wkt,
                        "parameters": {
                            "min_observations": min_obs.value,
                            "confidence_threshold": confidence.value,
                            "time_period": ";".join(selected_time_periods),
                            "directive_types": directive_values,
                            "include_historical": include_historical.value,
                            "generate_report": generate_report.value,
                        },
                    }

                    import httpx

                    async with httpx.AsyncClient() as http_client:
                        try:
                            response = await http_client.post(
                                f"{LOCAL_API_BASE_URL}/api/workflows/submit",
                                json=workflow_payload,
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            if response.status_code == 200:
                                result = response.json()
                                ui.notify(
                                    f'Workflow submitted! ID: {result["workflow_id"][:8]}...',
                                    type="positive",
                                )
                                # Fire-and-forget JS cleanup; do NOT await during navigation
                                ui.run_javascript(
                                    "if(window.drawnItems) window.drawnItems.clearLayers();",
                                    timeout=5.0,
                                )
                                ui.navigate.to("/workflows")
                            else:
                                ui.notify(f"Error: {response.text}", type="negative")
                        except Exception as e:
                            ui.notify(f"Error: {str(e)}", type="negative")

                ui.button("Submit Workflow", on_click=submit_workflow).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                ).props("icon=send")

            # Map Section
            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label("Select Analysis Area").classes(
                        "text-xl font-semibold text-gray-800"
                    )
                    ui.label("*").classes("required-asterisk text-xl")
                ui.label(
                    "Draw a rectangle or polygon on the map (Europe only)"
                ).classes("text-sm text-gray-500 mb-4")

                ui.html('<div id="map"></div>', sanitize=False).classes("w-full")

                ui.button(
                    "Clear Selection",
                    on_click=lambda: ui.run_javascript(
                        "if(window.drawnItems) { window.drawnItems.clearLayers(); window.geometryType = null; window.geometryWkt = null; var wktEl = document.getElementById('geometry-wkt'); if (wktEl) wktEl.textContent = 'WKT: None - Draw on map →'; }"
                    ),
                ).classes("mt-4 bmd-btn-secondary bmd-btn").props("icon=delete outline")

    # Initialize Leaflet map
    await client.connected()
    ui.run_javascript(
        """
        (() => {
            const tryInit = (retries) => {
                const mapEl = document.getElementById('map');
                if (!mapEl || !window.L || !window.L.Control || !window.L.Control.Draw) {
                    if (retries > 0) return setTimeout(() => tryInit(retries - 1), 100);
                    return;
                }
                if (window._bmdMap) return;

                window.geometryType = null;
                window.geometryWkt = null;

                const map = L.map('map').setView([50.0, 10.0], 4);

                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '© OpenStreetMap contributors'
                }).addTo(map);

                const europeBounds = L.latLngBounds(L.latLng(34.0, -25.0), L.latLng(72.0, 45.0));
                map.setMaxBounds(europeBounds);
                map.setMinZoom(3);

                window.drawnItems = new L.FeatureGroup();
                map.addLayer(window.drawnItems);

                const drawControl = new L.Control.Draw({
                    position: 'topright',
                    draw: {
                        polygon: {
                            allowIntersection: false,
                            showArea: true,
                            shapeOptions: { color: '#2ECC71', fillColor: '#2ECC71', fillOpacity: 0.3 }
                        },
                        rectangle: {
                            shapeOptions: { color: '#17A2B8', fillColor: '#17A2B8', fillOpacity: 0.3 }
                        },
                        circle: false,
                        circlemarker: false,
                        marker: false,
                        polyline: false
                    },
                    edit: { featureGroup: window.drawnItems }
                });
                map.addControl(drawControl);

                map.on(L.Draw.Event.CREATED, function(event) {
                    window.drawnItems.clearLayers();
                    const layer = event.layer;
                    window.drawnItems.addLayer(layer);

                    const coords = layer.getLatLngs()[0].map(function(ll) {
                        return [ll.lat, ll.lng];
                    });

                    window.geometryType = event.layerType;
                    const wktCoords = coords.map(function(c) { return c[1] + " " + c[0]; });
                    if (wktCoords.length && wktCoords[0] !== wktCoords[wktCoords.length - 1]) {
                        wktCoords.push(wktCoords[0]);
                    }
                    window.geometryWkt = "POLYGON ((" + wktCoords.join(", ") + "))";
                    const wktEl = document.getElementById('geometry-wkt');
                    if (wktEl) wktEl.textContent = "WKT: " + window.geometryWkt;
                    console.log('Geometry saved:', window.geometryData);
                });

                map.on(L.Draw.Event.DELETED, function() {
                    window.geometryType = null;
                    window.geometryWkt = null;
                    const wktEl = document.getElementById('geometry-wkt');
                    if (wktEl) wktEl.textContent = "WKT: None - Draw on map →";
                });

                window._bmdMap = map;
            };

            setTimeout(() => tryInit(50), 0);
            return true;
        })();
    """,
        timeout=5.0,
    )


# ============================================================================
# Workflows Page
# ============================================================================
@ui.page("/workflows")
async def workflows_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header("workflows")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Your Workflows").classes("text-3xl font-bold").style(
                "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
            )
            ui.button("Refresh", on_click=lambda: ui.navigate.to("/workflows")).classes(
                "bmd-btn-secondary bmd-btn"
            ).props("icon=refresh")

        workflows = get_user_workflows(user_id)
        import json

        await ui.run_javascript(
            """
            window.copyWorkflowId = async (text) => {
                try {
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(text);
                        return;
                    }
                } catch (err) {}
                const el = document.createElement('textarea');
                el.value = text;
                el.setAttribute('readonly', '');
                el.style.position = 'fixed';
                el.style.left = '-9999px';
                document.body.appendChild(el);
                el.select();
                try { document.execCommand('copy'); } catch (err) {}
                document.body.removeChild(el);
            };
            window.bindWorkflowIdCopyButtons = () => {
                document.querySelectorAll('[data-copy-id]').forEach((el) => {
                    if (el.dataset.copyBound) return;
                    el.dataset.copyBound = '1';
                    el.addEventListener('click', () => {
                        window.copyWorkflowId(el.dataset.copyId);
                    });
                });
            };
            """
        )

        if not workflows:
            with ui.card().classes("bmd-card p-8 w-full text-center"):
                ui.icon("science", size="4rem").classes("text-gray-300 mb-4")
                ui.label("No workflows submitted yet").classes("text-xl text-gray-500")
                ui.label("Create your first workflow to get started").classes(
                    "text-gray-400"
                )
                ui.button(
                    "+ New Workflow", on_click=lambda: ui.navigate.to("/select-workflow")
                ).classes("bmd-btn mt-4")
        else:
            with ui.card().classes("bmd-card p-6 w-full"):
                # Table header
                with ui.row().classes(
                    "w-full items-center py-3 border-b-2 border-gray-200 gap-4 font-semibold text-gray-600"
                ):
                    ui.label("ID").classes("w-32")
                    ui.label("Name").classes("flex-1")
                    ui.label("Species").classes("w-24")
                    ui.label("Ecosystem").classes("w-28")
                    ui.label("Status").classes("w-28")
                    ui.label("Created").classes("w-36")
                    ui.label("Actions").classes("w-32")

                for wf in workflows:
                    with ui.row().classes(
                        "w-full items-center py-3 border-b border-gray-100 gap-4"
                    ):
                        with ui.row().classes("w-32 items-center gap-2"):
                            ui.label(wf["workflow_id"][:12] + "...").classes(
                                "font-mono text-sm"
                            ).props(f'title="{wf["workflow_id"]}"')
                            ui.button(
                                icon="content_copy",
                                on_click=lambda: ui.notify(
                                    "Workflow ID copied", type="positive"
                                ),
                            ).props('flat round title="Copy ID"').classes(
                                "text-gray-500"
                            ).props(f"data-copy-id={json.dumps(wf['workflow_id'])}")
                        ui.label(wf["name"]).classes("font-semibold flex-1")
                        ui.label(wf.get("species_name") or "—").classes("w-24")

                        ecosystem = (wf.get("ecosystem_type") or "unknown").lower()
                        ecosystem_color = (
                            "green"
                            if ecosystem == "terrestrial"
                            else ("blue" if ecosystem == "freshwater" else "grey")
                        )
                        ui.badge(ecosystem.upper()).props(f"color={ecosystem_color}").classes(
                            "w-28"
                        )

                        status = wf["status"]
                        color = (
                            "green"
                            if status == "completed"
                            else (
                                "blue"
                                if status == "running"
                                else "orange" if status == "submitted" else "red"
                            )
                        )
                        ui.badge(status.upper()).props(f"color={color}").classes("w-28")

                        ui.label(
                            wf["created_at"][:16] if wf["created_at"] else "N/A"
                        ).classes("w-36 text-sm text-gray-500")

                        # --- Actions column with delete button and confirmation dialog ---
                        with ui.row().classes("w-32 items-center gap-2"):
                            if status == "completed" and wf.get("results"):
                                ui.button(
                                    "View",
                                    on_click=lambda wid=wf[
                                        "workflow_id"
                                    ]: ui.navigate.to(f"/results/{wid}"),
                                ).props("flat color=teal icon=visibility")

                            async def confirm_delete(
                                workflow_id=wf["workflow_id"], name=wf["name"]
                            ):
                                with ui.dialog() as dialog, ui.card().classes(
                                    "p-6 w-96"
                                ):
                                    ui.label("Delete Workflow").classes(
                                        "text-xl font-bold text-red-600 mb-2"
                                    )
                                    ui.label(
                                        f"Are you sure you want to permanently delete '{name}'?"
                                    ).classes("text-gray-700 mb-4")
                                    ui.label("This action cannot be undone.").classes(
                                        "text-sm text-gray-500 mb-4"
                                    )

                                    with ui.row().classes("justify-end gap-3"):
                                        ui.button(
                                            "Cancel", on_click=dialog.close
                                        ).props("flat")

                                        async def do_delete():
                                            token = app.storage.user.get("token")
                                            import httpx

                                            async with httpx.AsyncClient() as client:
                                                await client.delete(
                                                    f"{LOCAL_API_BASE_URL}/api/workflows/{workflow_id}",
                                                    headers={
                                                        "Authorization": f"Bearer {token}"
                                                    },
                                                )
                                            dialog.close()
                                            ui.notify(
                                                "Workflow deleted", type="positive"
                                            )
                                            ui.navigate.to("/workflows")

                                        ui.button(
                                            "Delete",
                                            on_click=do_delete,
                                        ).classes("bmd-btn-danger bmd-btn")

                                dialog.open()

                            ui.button(
                                icon="delete",
                                on_click=confirm_delete,
                            ).props("flat round color=red")
        await ui.run_javascript(
            "window.bindWorkflowIdCopyButtons && window.bindWorkflowIdCopyButtons();"
        )
    create_footer()


# ============================================================================
# Results Page
# ============================================================================
@ui.page("/results/{workflow_id}")
async def results_page(workflow_id: str):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        with ui.column().classes("w-full min-h-screen items-center justify-center"):
            ui.label("Workflow not found").classes("text-xl text-red-500")
            ui.button(
                "Back to Workflows", on_click=lambda: ui.navigate.to("/workflows")
            ).classes("bmd-btn mt-4")
        create_footer()
        return

    # Parse results
    import ast

    try:
        results = ast.literal_eval(workflow["results"]) if workflow["results"] else {}
    except:
        results = {"raw": workflow["results"]}

    with ui.column().classes("w-full min-h-screen"):
        # Header with back button
        with ui.row().classes("w-full bg-white shadow-sm p-4 items-center gap-4"):
            ui.button(
                icon="arrow_back", on_click=lambda: ui.navigate.to("/workflows")
            ).props("flat round")
            with ui.column().classes("gap-0"):
                ui.label("Analysis Results").classes("text-xl font-bold").style(
                    "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )
                ui.label(f"{workflow['name']}").classes("text-sm text-gray-500")

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
            # Workflow Info Card
            with ui.card().classes("bmd-card p-6 w-full"):
                ui.label("Workflow Details").classes(
                    "text-lg font-semibold text-gray-800 mb-4"
                )
                with ui.row().classes("gap-8 flex-wrap"):
                    with ui.column().classes("gap-1"):
                        ui.label("Workflow ID").classes("text-xs text-gray-500")
                        ui.label(workflow_id[:20] + "...").classes("font-mono text-sm")
                    with ui.column().classes("gap-1"):
                        ui.label("Species Group").classes("text-xs text-gray-500")
                        ui.label(workflow.get("species_name") or "—").classes("font-medium")
                    with ui.column().classes("gap-1"):
                        ui.label("Created").classes("text-xs text-gray-500")
                        ui.label(
                            workflow["created_at"][:19]
                            if workflow["created_at"]
                            else "N/A"
                        ).classes("font-medium")
                    with ui.column().classes("gap-1"):
                        ui.label("Status").classes("text-xs text-gray-500")
                        ui.badge("COMPLETED").props("color=green")

            if isinstance(results, dict) and "summary" in results:
                # Summary Section
                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Summary").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    with ui.row().classes("gap-8 justify-around"):
                        with ui.column().classes("items-center p-4"):
                            ui.label(str(results["summary"]["total_species"])).classes(
                                "text-4xl font-bold text-green-600"
                            )
                            ui.label("Species Detected").classes(
                                "text-sm text-gray-600"
                            )
                        with ui.column().classes("items-center p-4"):
                            ui.label(
                                f'{results["summary"]["total_occurrences"]:,}'
                            ).classes("text-4xl font-bold text-teal-600")
                            ui.label("Total Occurrences").classes(
                                "text-sm text-gray-600"
                            )
                        with ui.column().classes("items-center p-4"):
                            ui.label(f'{results["summary"]["area_km2"]:,.0f}').classes(
                                "text-4xl font-bold text-blue-600"
                            )
                            ui.label("Analysis Area (km²)").classes(
                                "text-sm text-gray-600"
                            )

                # Model Performance
                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Model Performance Metrics").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    with ui.row().classes("gap-6 justify-around"):
                        perf = results["model_performance"]
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['auc_score']:.3f}").classes(
                                "text-3xl font-bold text-green-600"
                            )
                            ui.label("AUC Score").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["auc_score"], show_value=False
                            ).classes("w-24").props("color=green")
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['tss_score']:.3f}").classes(
                                "text-3xl font-bold text-teal-600"
                            )
                            ui.label("TSS Score").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["tss_score"], show_value=False
                            ).classes("w-24").props("color=teal")
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['kappa']:.3f}").classes(
                                "text-3xl font-bold text-blue-600"
                            )
                            ui.label("Kappa").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["kappa"], show_value=False
                            ).classes("w-24").props("color=blue")

                with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
                    # Top Species
                    with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                        ui.label("Top Species by Habitat Suitability").classes(
                            "text-lg font-semibold text-gray-800 mb-4"
                        )
                        for i, species in enumerate(results.get("top_species", [])):
                            with ui.row().classes(
                                "w-full items-center justify-between py-3 border-b border-gray-100"
                            ):
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(f"{i+1}").classes(
                                        "w-6 h-6 rounded-full bg-green-100 text-green-700 text-center text-sm font-bold"
                                    )
                                    with ui.column().classes("gap-0"):
                                        ui.label(species["name"]).classes(
                                            "font-medium italic"
                                        )
                                        ui.label(
                                            f'{species["occurrences"]} occurrences'
                                        ).classes("text-xs text-gray-500")
                                with ui.column().classes("items-end"):
                                    ui.label(
                                        f'{species["habitat_suitability"]:.0%}'
                                    ).classes("text-lg font-bold text-green-600")
                                    ui.label("suitability").classes(
                                        "text-xs text-gray-500"
                                    )

                    # Environmental Variables
                    with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                        ui.label("Environmental Variable Importance").classes(
                            "text-lg font-semibold text-gray-800 mb-4"
                        )
                        for var_name, var_data in results.get(
                            "environmental_variables", {}
                        ).items():
                            with ui.column().classes("w-full py-2"):
                                with ui.row().classes("w-full justify-between mb-1"):
                                    ui.label(
                                        var_name.replace("_", " ")
                                        .replace("bio1 ", "Mean Temp ")
                                        .replace("bio12 ", "Annual Precip ")
                                        .title()
                                    ).classes("text-sm font-medium")
                                    ui.label(
                                        f'{var_data["contribution_pct"]}%'
                                    ).classes("text-sm font-bold text-teal-600")
                                ui.linear_progress(
                                    value=var_data["contribution_pct"] / 100,
                                    show_value=False,
                                ).classes("w-full").props("color=teal size=10px")
            else:
                # Fallback for raw results
                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Raw Results").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    ui.code(str(results)).classes("w-full")

            # Back button at bottom
            ui.button(
                "← Back to Workflows", on_click=lambda: ui.navigate.to("/workflows")
            ).classes("bmd-btn mt-4")
    create_footer()


# ============================================================================
# Root redirect
# ============================================================================
@ui.page("/")
def root_page():
    user_id = check_auth()
    create_footer()
    if user_id:
        return RedirectResponse("/workflows")
    return RedirectResponse("/login")


# ============================================================================
# Mount NiceGUI to FastAPI
# ============================================================================
ui.run_with(
    fastapi_app,
    title="BMD - Biodiversity Meets Data",
    favicon="🌿",
    storage_secret=SECRET_KEY
)
