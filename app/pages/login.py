"""Login page."""

from nicegui import ui

from ui_common import apply_bmd_theme, PageHeader
from ui_widgets import card_header


@ui.page("/login")
def login_page() -> None:
    apply_bmd_theme(header=PageHeader.NONE, public_auth=True)

    with ui.column().classes("w-full min-h-screen items-center p-8 overflow-visible"):
        with ui.column().classes("items-center gap-4 mt-10 mb-10 overflow-visible"):
            ui.label("BMD").classes("text-7xl font-bold leading-none text-green-600")
            ui.label("Biodiversity Analysis Tools").classes(
                "text-3xl font-semibold tracking-wide text-gray-700"
            )

        with ui.column().classes("w-full items-center"):
            with ui.card().classes("bmd-card p-8 w-full max-w-md items-center"):
                card_header("Welcome")
                ui.label("Sign in with your BMD account to continue.").classes(
                    "text-gray-500 text-center mb-6"
                )
                ui.button(
                    "Sign in with SSO",
                    on_click=lambda: ui.navigate.to("/api/auth/login"),
                ).props("icon=login").classes("w-full bmd-btn text-lg py-3")

    return None
