"""Signup page."""

from nicegui import app, ui

from auth_utils import create_access_token, hash_password
from database import create_user, get_user_by_email
from ui_common import apply_bmd_theme, create_footer, optional_label, required_label


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
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

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
