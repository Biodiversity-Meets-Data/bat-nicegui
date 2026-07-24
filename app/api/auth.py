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
    claims = token.get("userinfo")
    if claims is None:
        return RedirectResponse("/login")

    # Retrieve keycloak "subject" - the user's internal UUID in keycloak.
    keycloak_sub = claims.get("sub")
    if not keycloak_sub:
        return RedirectResponse("/login")
    keycloak_sub = cast(str, keycloak_sub)

    # Retrieve user email from Keycloak. An email must be set.
    email = claims.get("email")
    if not email:
        return RedirectResponse("/login")
    email = cast(str, email)

    # Retrieve user name from Keycloak. If missing, use email as username.
    name = claims.get("name") or claims.get("preferred_username") or email

    # An unverified email is not a trustworthy identifier - it must not be used
    # to reach an existing account, nor stored as a new account's identity.
    if claims.get("email_verified") is not True:
        return RedirectResponse("/login")

    # Check if the keycloak user already exists in the local database.
    user = get_user_by_keycloak_sub(keycloak_sub)
    if not user:
        # If the keycloak user does not exist locally yet, test if there is a
        # pre-existing user with the same email, and if yes, then link the
        # keycloak ID to this local account. This is essentially a "migration"
        # for pre-existing users.
        user = get_user_by_email(email)
        if user:
            set_user_keycloak_sub(user["user_id"], keycloak_sub)

    if user:
        # Case 1: the user already exists in the local database.
        user_id = user["user_id"]
    else:
        # Case 2: the user does not exist yet, and gets created.
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
