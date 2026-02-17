"""Login page."""

from nicegui import app, ui

from auth_utils import create_access_token, verify_password
from database import get_user_by_email
from ui_common import apply_bmd_theme, create_footer, required_label


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
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

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
