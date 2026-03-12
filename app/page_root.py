"""Root page redirect."""

from fastapi.responses import RedirectResponse
from nicegui import ui

from ui_common import check_auth, create_footer


@ui.page("/")
def root_page():
    user_id = check_auth()
    create_footer()
    if user_id:
        return RedirectResponse("/workflows")
    return RedirectResponse("/login")
