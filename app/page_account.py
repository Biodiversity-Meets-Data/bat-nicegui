"""Account settings page."""

import re

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from config import KEYCLOAK_REALM, KEYCLOAK_SERVER_URL
from database import (
    check_email_exists,
    DatabaseError,
    delete_user,
    get_user_by_id,
    update_user_profile,
)
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import optional_label, required_label


@ui.page("/account")
async def account_page() -> RedirectResponse | None:
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()

    user = get_user_by_id(user_id)
    if not user:
        ui.label("User not found").classes("text-xl text-red-500")
        return None

    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
        ui.label("Account Settings").classes("text-3xl font-bold").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )

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

            async def update_profile() -> None:
                """Update a user's profile in the database."""
                name = name_input.value.strip()
                email = email_input.value.strip()
                orcid = orcid_input.value.strip()

                # Verify user input.
                # ORCID is optional (can be an empty string), but when passed
                # it must match the ORCID format.
                if not name or not email:
                    ui.notify("Name and email are required", type="negative")
                    return
                if check_email_exists(email, exclude_user_id=user_id):
                    ui.notify("Email is already in use", type="negative")
                    return
                if orcid:
                    orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
                    if not re.match(orcid_pattern, orcid):
                        ui.notify("Invalid ORCID format", type="negative")
                        return

                # Update user profile in database.
                try:
                    update_user_profile(user_id, name, email, orcid)
                    app.storage.user["user_name"] = name
                    ui.notify("Profile updated successfully", type="positive")
                except DatabaseError as e:
                    ui.notify(f"Profile update failed: {e}", type="negative")

            ui.button("Save Changes", on_click=update_profile).classes("bmd-btn mt-6")

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Password & Login").classes(
                "text-xl font-semibold text-gray-800 mb-2"
            )
            ui.label(
                "Your password and login credentials are managed by your BMD "
                "SSO account, not here."
            ).classes("text-sm text-gray-600 mb-4")

            account_console_url = (
                f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/account"
            )
            ui.button(
                "Manage account on SSO",
                on_click=lambda: ui.navigate.to(account_console_url, new_tab=True),
            ).props("icon=open_in_new outline").classes("bmd-btn-secondary bmd-btn")

        with ui.card().classes("bmd-card p-6 w-full border-2 border-red-200"):
            ui.label("Danger Zone").classes("text-xl font-semibold text-red-600 mb-2")
            ui.label(
                "Once you delete your account, there is no going back. All your "
                "workflows will be permanently deleted. This only removes your "
                "local BMD data — your SSO account itself is not deleted."
            ).classes("text-sm text-gray-600 mb-4")

            async def confirm_delete() -> None:
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

                        async def do_delete() -> None:
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

    return None
