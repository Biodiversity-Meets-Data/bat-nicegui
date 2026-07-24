"""Authentication routes: Keycloak OIDC login/callback/logout."""

from typing import cast
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from nicegui import app as nicegui_app, ui

from auth_utils import create_access_token
from config import (
    KEYCLOAK_CLIENT_ID,
    KEYCLOAK_CLIENT_SECRET,
    KEYCLOAK_DISCOVERY_URL,
    LOCAL_API_BASE_URL,
)
from database import (
    create_user_from_keycloak,
    get_user_by_email,
    get_user_by_keycloak_sub,
    set_user_keycloak_sub,
)

router = APIRouter()
oauth = OAuth()
oauth.register(
    name="keycloak",
    server_metadata_url=KEYCLOAK_DISCOVERY_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    client_secret=KEYCLOAK_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/api/auth/login")
async def api_auth_login(request: Request) -> RedirectResponse:
    redirect_uri = f"{LOCAL_API_BASE_URL}/api/auth/callback"
    # The OAuth client is resolved by dynamic attribute lookup, so even with
    # authlib stubs installed its type degrades to Any and casting is needed.
    return cast(
        RedirectResponse,
        await oauth.keycloak.authorize_redirect(request, redirect_uri),
    )


@ui.page("/api/auth/callback", response_timeout=15.0)
async def api_auth_callback(request: Request) -> RedirectResponse:
    token = await oauth.keycloak.authorize_access_token(request)
    claims = token.get("userinfo") or {}
    keycloak_sub = claims.get("sub")
    if keycloak_sub is None:
        return RedirectResponse("/login")

    email = claims.get("email") or ""
    name = claims.get("name") or claims.get("preferred_username") or email

    user = get_user_by_keycloak_sub(keycloak_sub)
    if not user and email:
        user = get_user_by_email(email)
        if user:
            set_user_keycloak_sub(user["user_id"], keycloak_sub)

    if user:
        user_id = user["user_id"]
    else:
        user_id = create_user_from_keycloak(keycloak_sub, email, name)

    access_token = create_access_token(user_id)
    nicegui_app.storage.user["token"] = access_token
    nicegui_app.storage.user["user_id"] = user_id
    nicegui_app.storage.user["user_name"] = name
    nicegui_app.storage.user["kc_id_token"] = token.get("id_token")

    return RedirectResponse("/workflows")


@ui.page("/api/auth/logout", response_timeout=15.0)
async def api_auth_logout(request: Request) -> RedirectResponse:
    id_token = nicegui_app.storage.user.get("kc_id_token")
    nicegui_app.storage.user.clear()

    metadata = await oauth.keycloak.load_server_metadata()
    end_session_endpoint = metadata.get("end_session_endpoint")

    if not end_session_endpoint:
        return RedirectResponse("/login")

    params = {"post_logout_redirect_uri": f"{LOCAL_API_BASE_URL}/login"}
    if id_token:
        params["id_token_hint"] = id_token

    return RedirectResponse(f"{end_session_endpoint}?{urlencode(params)}")
