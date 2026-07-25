"""Application configuration values."""

import os
from pathlib import Path


def getenv_str(var_name: str, default: str = "") -> str:
    """Like os.getenv, but returns `default` when the var is unset or empty."""
    return os.getenv(var_name) or default


def getenv_bool(var_name: str) -> bool:
    return (os.getenv(var_name) or "false").lower() == "true"


SECRET_KEY = getenv_str("SECRET_KEY", "bmd-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

WORKFLOW_API_URL = getenv_str(
    "WORKFLOW_API_URL", "http://workflow-api:8002/api/v1/workflows"
)
LOCAL_API_BASE_URL = getenv_str("LOCAL_API_BASE_URL", "http://localhost:8080")

# Workflow submission API.
WORKFLOW_API_KEY = getenv_str(
    "WORKFLOW_API_KEY", "EpQaNpHS.EDed81RKaUno5Idj1AJgK2rLR7ieCb0h"
)
WORKFLOW_API_AUTH_HEADER = getenv_str("WORKFLOW_API_AUTH_HEADER", "Authorization")
WORKFLOW_API_AUTH_SCHEME = getenv_str("WORKFLOW_API_AUTH_SCHEME", "Bearer")
WORKFLOW_WEBHOOK_URL_TEMPLATE = getenv_str(
    "WORKFLOW_WEBHOOK_URL_TEMPLATE",
    "http://bmd-bat-app:8080/api/workflows/webhook/{workflow_id}",
)
WORKFLOW_DRY_RUN = getenv_bool("WORKFLOW_DRY_RUN")
WORKFLOW_FORCE = getenv_bool("WORKFLOW_FORCE")

# Keycloak authentication.
KEYCLOAK_SERVER_URL = getenv_str("KEYCLOAK_SERVER_URL")
KEYCLOAK_REALM = getenv_str("KEYCLOAK_REALM")
KEYCLOAK_CLIENT_ID = getenv_str("KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET = getenv_str("KEYCLOAK_CLIENT_SECRET")
KEYCLOAK_DISCOVERY_URL = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
