"""Account settings page."""

import re
from typing import Any

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from config import KEYCLOAK_REALM, KEYCLOAK_SERVER_URL
from database import (
    DatabaseError,
    delete_user,
    get_user_by_id,
    update_user_profile,
)
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import (
    Color,
    card_header,
    optional_text_input,
    page_title,
    readonly_text_input,
    required_text_input,
)


class UserAccountPage:
    """User account settings page: profile, sso (single sign-on), and account
    deletion.

    Instantiated once per visit (inside the page handler), after the user has
    been authenticated and their record fetched.
    """

    ROUTE = "/account"

    def __init__(self, user_id: str, user: dict[str, Any]) -> None:
        self.user_id = user_id
        self.user = user
        self.build_page()

    # ------------------------- Page construction --------------------------- #

    def build_page(self) -> None:
        """Build the page: title plus the three settings sections."""

        with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-6"):
            page_title("Account Settings")
            # Add page sections.
            self.add_profile_section()
            self.add_sso_info_section()
            self.add_danger_zone()

    def add_profile_section(self) -> None:
        """Adds the profile information section: name, email, ORCID."""

        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Profile Information")
            self.name_input = required_text_input(
                label="Full Name", value=self.user.get("name", "")
            )
            readonly_text_input(
                label="Email",
                value=self.user.get("email", ""),
                hint="Your email is managed by your BMD SSO account and cannot "
                "be changed here.",
            )
            self.orcid_input = optional_text_input(
                label="ORCID",
                value=self.user.get("orcid", "") or "",
                hint="ORCID identifier (format: 0000-0000-0000-0000)",
            )

            ui.button("Save Changes", on_click=self.update_profile).classes(
                "bmd-btn mt-6"
            )

    def add_sso_info_section(self) -> None:
        """Build the SSO (single sign-on) information section."""

        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Password and Login")
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

    def add_danger_zone(self) -> None:
        """Build the account-deletion section."""

        with ui.card().classes("bmd-card p-6 w-full border-2 border-red-200"):
            card_header("Danger Zone", color=Color.RED)
            ui.label(
                "Once you delete your account, there is no going back. "
                "All your workflows will be permanently deleted. "
                "Note that this only removes your local BMD data - your SSO "
                "account itself is not deleted."
            ).classes("text-sm text-gray-600 mb-4")

            ui.button("Delete Account", on_click=self.confirm_deletion).classes(
                "bmd-btn-danger bmd-btn"
            ).props("icon=delete")

    # -------------------------- Event handlers ----------------------------- #

    async def update_profile(self) -> None:
        """Validate the profile inputs and persist them to the database."""

        name = (self.name_input.value or "").strip()
        orcid = (self.orcid_input.value or "").strip()

        # Verify user input.
        # ORCID is optional (can be an empty string), but when passed
        # it must match the ORCID format.
        if not name:
            ui.notify("Name is required", type="negative")
            return
        if orcid:
            orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
            if not re.match(orcid_pattern, orcid):
                ui.notify("Invalid ORCID format", type="negative")
                return

        # Update user profile in database.
        try:
            update_user_profile(self.user_id, name, orcid)
            app.storage.user["user_name"] = name
            ui.notify("Profile updated successfully", type="positive")
        except DatabaseError as e:
            ui.notify(f"Profile update failed: {e}", type="negative")

    async def confirm_deletion(self) -> None:
        """Open a confirmation dialog for user account deletion."""

        with ui.dialog() as dialog, ui.card().classes("p-6"):
            ui.label("Delete Account").classes("text-xl font-bold text-red-600")
            ui.label(
                "Are you sure you want to delete your account? This action cannot be undone."
            ).classes("text-gray-600")

            # To avoid mistakes, user must type email before deletion.
            confirm_email_input = required_text_input(
                label="Type your email to confirm:", placeholder=self.user["email"]
            )

            with ui.row().classes("gap-4 justify-end"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                # The dialog and its confirm-email input are transient to this
                # interaction, so this handler stays local rather than becoming
                # a method with instance-level state.
                async def do_delete() -> None:
                    if confirm_email_input.value != self.user["email"]:
                        ui.notify("Email doesn't match", type="negative")
                        return

                    delete_user(self.user_id)
                    app.storage.user.clear()
                    dialog.close()
                    ui.notify("Account deleted", type="info")
                    ui.navigate.to("/login")

                ui.button("Delete Account", on_click=do_delete).classes(
                    "bmd-btn-danger bmd-btn"
                )

        dialog.open()

    # ---------------------- Page Route registration ------------------------ #

    @classmethod
    def register(cls) -> None:
        """Register the page's route.

        Add <cls>.register() at the end of the page's module so that the
        method gets called when the module is imported.
        """

        @ui.page(cls.ROUTE)
        async def _render_page() -> RedirectResponse | None:

            # Page is only accessible to authenticated users.
            user_id = check_auth()
            if not user_id:
                return RedirectResponse("/login")

            # Add base page styling (theme).
            apply_bmd_theme()

            # If user does not exist in the database, the page displays
            # only a short warning message.
            user = get_user_by_id(user_id)
            if not user:
                ui.label("User not found").classes("text-xl text-red-500")
                return None

            # Build the page by creating a new instance of the class.
            cls(user_id, user)
            return None


UserAccountPage.register()
