"""Root page redirect."""

from fastapi.responses import RedirectResponse
from nicegui import ui

from ui_common import check_auth


@ui.page("/")
def root_page() -> RedirectResponse:
    user_id = check_auth()
    if user_id:
        return RedirectResponse("/workflows")
    return RedirectResponse("/login")
