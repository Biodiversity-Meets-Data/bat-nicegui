"""UI page registration."""


def register_ui_pages() -> None:
    import importlib

    import page_account  # noqa: F401
    import page_login  # noqa: F401
    import page_results  # noqa: F401
    import page_root  # noqa: F401
    import page_select_workflow  # noqa: F401
    import page_workflows  # noqa: F401

    from bats.registry import BAT_REGISTRY

    # Register each BAT page by importing its module.
    for bat in BAT_REGISTRY:
        importlib.import_module(bat.module_path)
