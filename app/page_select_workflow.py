"""BAT (Biodiversity Analysis Tool) selection page.

BATs are grouped in tabs corresponding to ecosystem categories. Each BAT is
presented as a tile/card with an icon and a short description. Clicking on
the tile/card opens the corresponding BAT page.
"""

from fastapi.responses import RedirectResponse
from nicegui import ui

from bats.registry import EcosystemCategory, Bat, bats_by_category
from ui_common import apply_bmd_theme, check_auth


def render_bat_card(bat: Bat) -> None:
    """Renders a single BAT tile/card."""

    async def show_about() -> None:
        with ui.dialog() as dialog, ui.card().classes("p-6 max-w-2xl"):
            ui.markdown(bat.about_md)
            ui.button("Close", on_click=dialog.close).classes("bmd-btn mt-4")
        dialog.open()

    card = ui.card().classes("bat-card p-4")
    card.on("click", lambda: ui.navigate.to(bat.route))

    with card, ui.column().classes("w-full h-full items-center justify-between gap-2"):
        with ui.column().classes("w-full items-center gap-1"):
            ui.icon(bat.icon).classes("bat-card-icon")
            ui.label(bat.label).classes(
                "text-base font-semibold text-gray-800 text-center"
            )
            ui.label(bat.description).classes(
                "text-xs text-gray-600 text-center bat-card-desc"
            )
        with ui.column().classes("items-center gap-1"):
            # `click.stop` keeps the About click from bubbling to the card's
            # launch handler. Do not also pass `on_click=` -- that would drop
            # the modifier.
            ui.button("About").props("outline size=sm").on("click.stop", show_about)


@ui.page("/select-workflow")
async def select_workflow_page() -> RedirectResponse | None:

    # The page is only accessible to authenticated users.
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
        ui.label("Biodiversity Analysis Tools").classes(
            "text-3xl font-bold mb-2"
        ).style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )
        ui.label("Select a category, then choose a tool.").classes(
            "text-lg text-gray-600 mb-2"
        )

        with ui.tabs().classes("w-full") as tabs:
            for category in EcosystemCategory:
                ui.tab(category.slug, label=category.label, icon=category.icon)

        default_category = next(iter(EcosystemCategory))
        with ui.tab_panels(tabs, value=default_category.slug).classes(
            "w-full bmd-card"
        ):
            for category in EcosystemCategory:
                with ui.tab_panel(category.slug):
                    bats = bats_by_category(category)
                    if not bats:
                        ui.label("No tools available yet — coming soon.").classes(
                            "text-sm text-gray-500 p-4"
                        )
                    else:
                        with ui.row().classes("w-full gap-4 flex-wrap p-2"):
                            for bat in bats:
                                render_bat_card(bat)

    return None
