"""
BMD - Biodiversity Meets Data
A NiceGUI + FastAPI application for biodiversity analysis workflows
"""

import os
import uuid
import asyncio
import secrets
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext
from nicegui import ui, app, Client

from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    create_workflow,
    get_user_workflows,
    update_workflow_status,
    get_workflow_by_id,
)

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "bmd-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
WORKFLOW_WAIT_TIME = int(os.getenv("WORKFLOW_WAIT_TIME", "20"))  # seconds

app.add_static_files("/static", "static")
# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# BMD Theme Colors (from logo)
BMD_COLORS = {
    "primary_green": "#2ECC71",
    "dark_green": "#1A9F53",
    "teal": "#17A2B8",
    "blue": "#0077B6",
    "gradient_start": "#2ECC71",
    "gradient_end": "#0077B6",
    "bg_light": "#F0F9F4",
    "bg_dark": "#0A1F14",
    "text_dark": "#1A3A2A",
    "text_light": "#E8F5E9",
}


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
    species_group: str
    date_range_start: str
    date_range_end: str
    geometry_type: str
    geometry_coords: list
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
async def lifespan(app: FastAPI):
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

    workflow_id = str(uuid.uuid4())

    # Print the workflow object as requested
    print("=" * 60)
    print(f"WORKFLOW SUBMITTED - ID: {workflow_id}")
    print(f"User ID: {user_id}")
    print(f"Name: {workflow.name}")
    print(f"Description: {workflow.description}")
    print(f"Species Group: {workflow.species_group}")
    print(f"Date Range: {workflow.date_range_start} to {workflow.date_range_end}")
    print(f"Geometry Type: {workflow.geometry_type}")
    print(f"Geometry Coords: {workflow.geometry_coords}")
    print(f"Parameters: {workflow.parameters}")
    print("=" * 60)

    # Create workflow in database
    create_workflow(
        workflow_id=workflow_id,
        user_id=user_id,
        name=workflow.name,
        description=workflow.description,
        species_group=workflow.species_group,
        date_range_start=workflow.date_range_start,
        date_range_end=workflow.date_range_end,
        geometry_type=workflow.geometry_type,
        geometry_coords=str(workflow.geometry_coords),
        parameters=str(workflow.parameters),
        status="submitted",
    )

    # Simulate workflow processing (in production, this would be an actual API call)
    asyncio.create_task(simulate_workflow_processing(workflow_id))

    return {"workflow_id": workflow_id, "status": "submitted"}


async def simulate_workflow_processing(workflow_id: str):
    """Simulate workflow processing with configurable wait time"""
    update_workflow_status(workflow_id, "running")
    await asyncio.sleep(WORKFLOW_WAIT_TIME)

    # Simulate SDM results
    import random

    results = {
        "summary": {
            "total_species": random.randint(15, 45),
            "total_occurrences": random.randint(500, 5000),
            "area_km2": round(random.uniform(1000, 50000), 2),
        },
        "model_performance": {
            "auc_score": round(random.uniform(0.75, 0.95), 3),
            "tss_score": round(random.uniform(0.5, 0.8), 3),
            "kappa": round(random.uniform(0.4, 0.7), 3),
        },
        "top_species": [
            {
                "name": "Quercus robur",
                "occurrences": random.randint(100, 500),
                "habitat_suitability": round(random.uniform(0.6, 0.95), 2),
            },
            {
                "name": "Fagus sylvatica",
                "occurrences": random.randint(80, 400),
                "habitat_suitability": round(random.uniform(0.5, 0.9), 2),
            },
            {
                "name": "Pinus sylvestris",
                "occurrences": random.randint(60, 300),
                "habitat_suitability": round(random.uniform(0.4, 0.85), 2),
            },
            {
                "name": "Betula pendula",
                "occurrences": random.randint(40, 200),
                "habitat_suitability": round(random.uniform(0.3, 0.8), 2),
            },
            {
                "name": "Picea abies",
                "occurrences": random.randint(20, 150),
                "habitat_suitability": round(random.uniform(0.25, 0.75), 2),
            },
        ],
        "environmental_variables": {
            "bio1_mean_temp": {
                "importance": round(random.uniform(0.15, 0.35), 3),
                "contribution_pct": round(random.uniform(20, 40), 1),
            },
            "bio12_annual_precip": {
                "importance": round(random.uniform(0.1, 0.25), 3),
                "contribution_pct": round(random.uniform(15, 30), 1),
            },
            "elevation": {
                "importance": round(random.uniform(0.08, 0.2), 3),
                "contribution_pct": round(random.uniform(10, 25), 1),
            },
            "soil_type": {
                "importance": round(random.uniform(0.05, 0.15), 3),
                "contribution_pct": round(random.uniform(5, 15), 1),
            },
        },
        "analysis_timestamp": datetime.utcnow().isoformat(),
    }
    update_workflow_status(workflow_id, "completed", results=str(results))


@fastapi_app.post("/api/workflows/webhook/{workflow_id}")
async def workflow_webhook(workflow_id: str, webhook_data: WorkflowWebhook):
    """Webhook endpoint called by Argo Workflow when job completes"""
    print(f"WEBHOOK RECEIVED for workflow {workflow_id}")
    print(f"Status: {webhook_data.status}")
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


# NiceGUI UI Components


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
            background: linear-gradient(135deg, #F0F9F4 0%, #E3F2E8 50%, #D4EEE8 100%) !important;
            min-height: 100vh;
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
        
        .bmd-input {
            border: 2px solid #E8F5E9;
            border-radius: 12px;
            padding: 12px 16px;
            font-family: 'Outfit', sans-serif;
            transition: border-color 0.3s ease;
        }
        
        .bmd-input:focus {
            border-color: #2ECC71;
            outline: none;
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
        
        .status-submitted { color: #F39C12; font-weight: 600; }
        .status-running { color: #17A2B8; font-weight: 600; }
        .status-completed { color: #2ECC71; font-weight: 600; }
        .status-failed { color: #E74C3C; font-weight: 600; }
        
        .workflow-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
        }
        
        .workflow-table th {
            background: linear-gradient(135deg, #2ECC71 0%, #17A2B8 100%);
            color: white;
            padding: 16px;
            font-weight: 600;
            text-align: left;
        }
        
        .workflow-table th:first-child { border-radius: 12px 0 0 0; }
        .workflow-table th:last-child { border-radius: 0 12px 0 0; }
        
        .workflow-table td {
            padding: 14px 16px;
            border-bottom: 1px solid #E8F5E9;
        }
        
        .workflow-table tr:hover td {
            background: #F0F9F4;
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
    </style>
    """
    )

def create_header(current_page: str = ""):
    """Create the BMD header with navigation"""
    with ui.header().classes("bmd-header items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            ui.image("/static/logo.png").classes("w-10 h-10 object-contain")
            with ui.column().classes("gap-0"):
                ui.label("BMD").classes("bmd-logo-text")
                ui.label("Biodiversity Meets Data").classes("bmd-subtitle")

        with ui.row().classes("gap-3 items-center"):
            ui.button("+ New Workflow", on_click=lambda: ui.navigate.to("/create")).props(
                "unelevated rounded" + (" color=white text-color=primary" if current_page != "create" else "")
            ).classes("font-semibold")
            
            ui.link("Workflows", "/workflows").classes(
                f'nav-link {"active" if current_page == "workflows" else ""}'
            )
            ui.button("Logout", on_click=lambda: logout()).props("flat text-color=white")
            


async def logout():
    app.storage.user.clear()
    ui.navigate.to("/login")


def check_auth() -> Optional[str]:
    """Check if user is authenticated"""
    token = app.storage.user.get("token")
    if not token:
        return None
    user_id = verify_token(token)
    return user_id


# Login Page
@ui.page("/login")
def login_page():
    apply_bmd_theme()

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
        ui.navigate.to("/create")

    with ui.column().classes("w-full min-h-screen items-center justify-center p-8"):
        with ui.card().classes("bmd-card p-8 w-full max-w-md"):
            with ui.column().classes("items-center gap-2 mb-8"):
                ui.image("/static/logo.png").classes("w-24 h-24")
                ui.label("BMD").classes("text-3xl font-bold").style(
                    "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )
                ui.label("Biodiversity Analysis Tool").classes("text-gray-500")

            ui.label("Welcome Back").classes(
                "text-2xl font-semibold text-gray-800 mb-4"
            )

            email_input = ui.input("Email").props("outlined").classes("w-full mb-4")
            password_input = (
                ui.input("Password", password=True)
                .props("outlined")
                .classes("w-full mb-6")
            )
            password_input.on("keydown.enter", do_login)

            ui.button("Sign In", on_click=do_login).classes(
                "w-full bmd-btn text-lg py-3"
            )

            with ui.row().classes("w-full justify-center mt-4 gap-1"):
                ui.label("Don't have an account?").classes("text-gray-500")
                ui.link("Sign up", "/signup").classes("text-teal-600 font-semibold")


# Signup Page
@ui.page("/signup")
def signup_page():
    apply_bmd_theme()

    async def do_signup():
        name = name_input.value
        email = email_input.value
        password = password_input.value
        confirm = confirm_input.value

        if not all([name, email, password, confirm]):
            ui.notify("Please fill in all fields", type="negative")
            return

        if password != confirm:
            ui.notify("Passwords do not match", type="negative")
            return

        if len(password) < 6:
            ui.notify("Password must be at least 6 characters", type="negative")
            return

        existing = get_user_by_email(email)
        if existing:
            ui.notify("Email already registered", type="negative")
            return

        hashed_pw = hash_password(password)
        user_id = create_user(email, hashed_pw, name)
        token = create_access_token(user_id)

        app.storage.user["token"] = token
        app.storage.user["user_id"] = user_id
        app.storage.user["user_name"] = name
        ui.navigate.to("/create")

    with ui.column().classes("w-full min-h-screen items-center justify-center p-8"):
        with ui.card().classes("bmd-card p-8 w-full max-w-md"):
            with ui.column().classes("items-center gap-2 mb-8"):
                ui.image("/static/logo.png").classes("w-24 h-24")
                ui.label("BMD").classes("text-3xl font-bold").style(
                    "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )
                ui.label("Biodiversity Analysis Tool").classes("text-gray-500")

            ui.label("Create Account").classes(
                "text-2xl font-semibold text-gray-800 mb-4"
            )

            name_input = ui.input("Full Name").props("outlined").classes("w-full mb-4")
            email_input = ui.input("Email").props("outlined").classes("w-full mb-4")
            password_input = (
                ui.input("Password", password=True)
                .props("outlined")
                .classes("w-full mb-4")
            )
            confirm_input = (
                ui.input("Confirm Password", password=True)
                .props("outlined")
                .classes("w-full mb-6")
            )
            confirm_input.on("keydown.enter", do_signup)

            ui.button("Create Account", on_click=do_signup).classes(
                "w-full bmd-btn text-lg py-3"
            )

            with ui.row().classes("w-full justify-center mt-4 gap-1"):
                ui.label("Already have an account?").classes("text-gray-500")
                ui.link("Sign in", "/login").classes("text-teal-600 font-semibold")


# Analysis Page
@ui.page("/create")
async def analysis_page(client: Client):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    create_header("create")

    # Store geometry data
    geometry_data = {"type": None, "coords": []}

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        ui.label("Submit Analysis Workflow").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

        with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
            # Form Section
            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                ui.label("Workflow Parameters").classes(
                    "text-xl font-semibold mb-4 text-gray-800"
                )

                name_input = (
                    ui.input("Workflow Name", placeholder="e.g., Alpine Species Survey")
                    .props("outlined")
                    .classes("w-full mb-4")
                )

                desc_input = (
                    ui.textarea("Description", placeholder="Describe your analysis...")
                    .props("outlined rows=3")
                    .classes("w-full mb-4")
                )

                species_select = (
                    ui.select(
                        options=[
                            "Birds",
                            "Mammals",
                            "Reptiles",
                            "Amphibians",
                            "Fish",
                            "Invertebrates",
                            "Plants",
                            "Fungi",
                            "All",
                        ],
                        value="All",
                        label="Species Group",
                    )
                    .props("outlined")
                    .classes("w-full mb-4")
                )

                with ui.row().classes("w-full gap-4 mb-4"):
                    date_start = (
                        ui.input("Start Date")
                        .props("outlined type=date")
                        .classes("flex-1")
                    )
                    date_end = (
                        ui.input("End Date")
                        .props("outlined type=date")
                        .classes("flex-1")
                    )

                ui.label("Additional Parameters").classes(
                    "text-sm font-semibold text-gray-600 mb-2"
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

                geometry_label = ui.label("Selected Area: None").classes(
                    "text-sm text-gray-600 mt-4 p-3 bg-gray-50 rounded-lg"
                )

                async def submit_workflow():
                    if not name_input.value:
                        ui.notify("Please enter a workflow name", type="warning")
                        return

                    # Get geometry data directly from JavaScript
                    geo_json = await ui.run_javascript(
                        "return JSON.stringify(window.geometryData)"
                    )

                    if not geo_json or geo_json == "null":
                        ui.notify("Please draw an area on the map", type="warning")
                        return

                    import json

                    try:
                        geo_data = json.loads(geo_json)
                    except:
                        ui.notify("Invalid geometry data", type="warning")
                        return

                    token = app.storage.user.get("token")

                    workflow_payload = {
                        "name": name_input.value,
                        "description": desc_input.value or "",
                        "species_group": species_select.value,
                        "date_range_start": date_start.value or "",
                        "date_range_end": date_end.value or "",
                        "geometry_type": geo_data.get("type"),
                        "geometry_coords": geo_data.get("coords", []),
                        "parameters": {
                            "min_observations": min_obs.value,
                            "confidence_threshold": confidence.value,
                            "include_historical": include_historical.value,
                            "generate_report": generate_report.value,
                        },
                    }

                    # Submit via API
                    import httpx

                    async with httpx.AsyncClient() as http_client:
                        try:
                            response = await http_client.post(
                                "http://localhost:8080/api/workflows/submit",
                                json=workflow_payload,
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            if response.status_code == 200:
                                result = response.json()
                                ui.notify(
                                    f'Workflow submitted successfully! ID: {result["workflow_id"][:8]}...',
                                    type="positive",
                                )
                                # Clear form
                                name_input.value = ""
                                desc_input.value = ""
                                geometry_label.text = "Selected Area: None"
                                await ui.run_javascript(
                                    "if(window.drawnItems) window.drawnItems.clearLayers();"
                                )
                            else:
                                ui.notify(f"Error: {response.text}", type="negative")
                        except Exception as e:
                            ui.notify(
                                f"Error submitting workflow: {str(e)}", type="negative"
                            )

                ui.button("Submit Workflow", on_click=submit_workflow).classes(
                    "w-full bmd-btn text-lg py-3 mt-6"
                ).props("icon=send")

            # Map Section
            with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                ui.label("Select Analysis Area").classes(
                    "text-xl font-semibold mb-2 text-gray-800"
                )
                ui.label(
                    "Draw a rectangle or polygon on the map (Europe only)"
                ).classes("text-sm text-gray-500 mb-4")

                map_container = ui.html('<div id="map"></div>', sanitize=False).classes(
                    "w-full"
                )

                ui.button(
                    "Clear Selection",
                    on_click=lambda: ui.run_javascript(
                        "if(window.drawnItems) window.drawnItems.clearLayers(); "
                        'document.getElementById("geometry-data").value = "";'
                    ),
                ).classes("mt-4 bmd-btn-secondary bmd-btn").props("icon=delete outline")

    # Hidden input to receive geometry data from JavaScript
    geometry_input = ui.input("").classes("hidden").props("id=geometry-data")

    def update_geometry(e):
        import json

        try:
            if e.value:
                data = json.loads(e.value)
                geometry_data["type"] = data.get("type")
                geometry_data["coords"] = data.get("coords", [])
                geometry_label.text = f"Selected Area: {data.get('type', 'Unknown')} with {len(data.get('coords', [[]]))} points"
        except:
            pass

    geometry_input.on("change", update_geometry)

    # Initialize Leaflet map with draw controls
    await client.connected()
    ui.run_javascript(
        """
        // Store geometry data globally
        window.geometryData = null;
        
        // Initialize map centered on Europe
        var map = L.map('map').setView([50.0, 10.0], 4);
        
        // Add OpenStreetMap tiles
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Restrict to Europe bounds
        var europeBounds = L.latLngBounds(
            L.latLng(34.0, -25.0),
            L.latLng(72.0, 45.0)
        );
        map.setMaxBounds(europeBounds);
        map.setMinZoom(3);
        
        // Initialize draw layer
        window.drawnItems = new L.FeatureGroup();
        map.addLayer(window.drawnItems);
        
        // Add draw controls
        var drawControl = new L.Control.Draw({
            position: 'topright',
            draw: {
                polygon: {
                    allowIntersection: false,
                    showArea: true,
                    shapeOptions: {
                        color: '#2ECC71',
                        fillColor: '#2ECC71',
                        fillOpacity: 0.3
                    }
                },
                rectangle: {
                    shapeOptions: {
                        color: '#17A2B8',
                        fillColor: '#17A2B8',
                        fillOpacity: 0.3
                    }
                },
                circle: false,
                circlemarker: false,
                marker: false,
                polyline: false
            },
            edit: {
                featureGroup: window.drawnItems
            }
        });
        map.addControl(drawControl);
        
        // Handle draw events
        map.on(L.Draw.Event.CREATED, function(event) {
            window.drawnItems.clearLayers();
            var layer = event.layer;
            window.drawnItems.addLayer(layer);
            
            var coords = layer.getLatLngs()[0].map(function(ll) {
                return [ll.lat, ll.lng];
            });
            
            window.geometryData = {
                type: event.layerType,
                coords: coords
            };
            
            console.log('Geometry saved:', window.geometryData);
        });
        
        map.on(L.Draw.Event.DELETED, function() {
            window.geometryData = null;
        });
    """
    )


# Workflows Page# Workflows Page
@ui.page("/workflows")
async def workflows_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    create_header("workflows")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Submitted Workflows").classes("text-3xl font-bold").style(
                "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
            )
            ui.button("Refresh", on_click=lambda: ui.navigate.to("/workflows")).classes(
                "bmd-btn-secondary bmd-btn"
            ).props("icon=refresh")

        workflows = get_user_workflows(user_id)

        if not workflows:
            with ui.card().classes("bmd-card p-8 w-full text-center"):
                ui.icon("science", size="4rem").classes("text-gray-300 mb-4")
                ui.label("No workflows submitted yet").classes("text-xl text-gray-500")
                ui.label(
                    "Go to the Analysis page to submit your first workflow"
                ).classes("text-gray-400")
                ui.button(
                    "Start Analysis", on_click=lambda: ui.navigate.to("/create")
                ).classes("bmd-btn mt-4")
        else:
            with ui.card().classes("bmd-card p-6 w-full"):
                for wf in workflows:
                    with ui.row().classes(
                        "w-full items-center py-3 border-b border-gray-100 gap-4"
                    ):
                        ui.label(wf["workflow_id"][:12] + "...").classes(
                            "font-mono text-sm w-32"
                        )
                        ui.label(wf["name"]).classes("font-semibold flex-1")
                        ui.label(wf["species_group"]).classes("w-24")

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
                        ui.badge(status.upper()).props(f"color={color}")

                        ui.label(
                            wf["created_at"][:16] if wf["created_at"] else "N/A"
                        ).classes("w-36 text-sm text-gray-500")

                        if status == "completed" and wf.get("results"):
                            ui.button(
                                "View Results",
                                on_click=lambda wid=wf["workflow_id"]: ui.navigate.to(
                                    f"/results/{wid}"
                                ),
                            ).props("flat color=teal icon=visibility")
                        elif status == "running":
                            ui.spinner(size="sm").classes("w-32")
                        else:
                            ui.label("").classes("w-32")


# Results Page
@ui.page("/results/{workflow_id}")
async def results_page(workflow_id: str):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        ui.label("Workflow not found").classes("text-xl text-red-500")
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
                        ui.label(workflow["species_group"]).classes("font-medium")
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


# Root redirect
@ui.page("/")
def root_page():
    user_id = check_auth()
    if user_id:
        return RedirectResponse("/craete")
    return RedirectResponse("/login")


# Mount NiceGUI to FastAPI
""" ui.run_with(
    fastapi_app,
    title='BMD - Biodiversity Meets Data',
    favicon='🌿',
    storage_secret=SECRET_KEY,
    host='0.0.0.0',
    port=8080
) """
# Mount NiceGUI to FastAPI
ui.run_with(
    fastapi_app,
    title="BMD - Biodiversity Meets Data",
    favicon="🌿",
    storage_secret=SECRET_KEY,
)
