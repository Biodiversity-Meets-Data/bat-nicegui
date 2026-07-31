"""App UI page registration."""

import importlib

from bats.registry import BAT_REGISTRY


def register_ui_pages() -> None:
    """Register all application UI routes with the server.

    Importing a page module runs its @ui.page route decorators, so importing
    each page module is what performs the registration.
    """
    from pages import (  # noqa: F401
        account,
        login,
        results,
        root,
        select_workflow,
        workflows,
    )

    # Register each BAT page by importing its module.
    for bat in BAT_REGISTRY:
        importlib.import_module(bat.module_path)
