"""Application configuration values."""

import os
from pathlib import Path

SECRET_KEY = os.getenv("SECRET_KEY", "bmd-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

WORKFLOW_API_URL = os.getenv(
    "WORKFLOW_API_URL", "http://workflow-api:8002/api/v1/workflows"
)
LOCAL_API_BASE_URL = os.getenv("LOCAL_API_BASE_URL", "http://localhost:8080")
WORKFLOW_API_KEY = os.getenv(
    "WORKFLOW_API_KEY", "EpQaNpHS.EDed81RKaUno5Idj1AJgK2rLR7ieCb0h"
)
WORKFLOW_API_AUTH_HEADER = os.getenv("WORKFLOW_API_AUTH_HEADER", "Authorization")
WORKFLOW_API_AUTH_SCHEME = os.getenv("WORKFLOW_API_AUTH_SCHEME", "Bearer")
WORKFLOW_WEBHOOK_URL_TEMPLATE = os.getenv(
    "WORKFLOW_WEBHOOK_URL_TEMPLATE",
    "http://bmd-bat-app:8080/api/workflows/webhook/{workflow_id}",
)
WORKFLOW_DRY_RUN = os.getenv("WORKFLOW_DRY_RUN", "false").lower() == "true"
WORKFLOW_FORCE = os.getenv("WORKFLOW_FORCE", "false").lower() == "true"

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
