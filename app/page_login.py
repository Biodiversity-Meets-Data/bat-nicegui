"""Login page."""

from nicegui import ui

from ui_common import apply_bmd_theme, create_footer


@ui.page("/login")
def login_page() -> None:
    apply_bmd_theme()
    ui.run_javascript("document.body.classList.add('public-auth')")

    with ui.column().classes("w-full min-h-screen items-center p-8 overflow-visible"):
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tool").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

        with ui.column().classes("w-full items-center"):
            with ui.card().classes("bmd-card p-8 w-full max-w-md items-center"):
                ui.label("Welcome").classes("text-2xl font-semibold text-gray-800 mb-4")
                ui.label("Sign in with your BMD account to continue.").classes(
                    "text-gray-500 text-center mb-6"
                )

                ui.button(
                    "Sign in with SSO",
                    on_click=lambda: ui.navigate.to("/api/auth/login"),
                ).props("icon=login").classes("w-full bmd-btn text-lg py-3")
    create_footer()
