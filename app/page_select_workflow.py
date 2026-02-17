"""Workflow selection page."""

from fastapi.responses import RedirectResponse
from nicegui import ui

from ui_common import apply_bmd_theme, check_auth, create_footer, create_header


@ui.page("/select-workflow")
async def select_workflow_page():
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")
    create_header()

    terrestrial_about_md = """
## Terrestrial Ecosystems

Analyze biodiversity patterns across land-based ecosystems including forests, grasslands, mountains, and urban areas.

### Features:
- **Species Distribution Modeling** - Predict suitable habitats for terrestrial species
- **Multi-scale Analysis** - From local to continental scales
- **Environmental Variables** - Temperature, precipitation, elevation, soil types
- **Temporal Analysis** - Historical and current data integration

### Typical Use Cases:
- Forest biodiversity assessments
- Conservation planning for protected areas
- Climate change impact studies
- Species range predictions
"""

    freshwater_about_md = """
## Freshwater Ecosystems

Analyze biodiversity in rivers, lakes, wetlands, and other freshwater habitats.

### Features:
- **Aquatic Species Modeling** - Fish, amphibians, invertebrates
- **Hydrological Integration** - Water quality, flow patterns
- **Habitat Connectivity** - River network analysis
- **Invasive Species Tracking** - Monitor non-native species spread

### Status:
🚧 **Coming Soon** - This workflow is currently under development and will be available in a future release.
"""

    with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-6"):
        ui.label("Select Workflow Type").classes("text-3xl font-bold mb-2").style(
            "background: linear-gradient(135deg, #2ECC71, #0077B6); "
            "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
        )
        ui.label("Choose the ecosystem type for your biodiversity analysis").classes(
            "text-lg text-gray-600 mb-6"
        )

        with ui.row().classes("w-full gap-8 flex-wrap lg:flex-nowrap"):
            with ui.card().classes("ecosystem-card p-8 flex-1 min-w-80"):
                with ui.column().classes("w-full items-center gap-4"):
                    ui.icon("forest").classes("ecosystem-icon")
                    ui.label("Terrestrial").classes("text-2xl font-bold text-gray-800")
                    ui.label(
                        "Land-based ecosystems: forests, grasslands, mountains"
                    ).classes("text-sm text-gray-600 text-center")

                    with ui.row().classes("w-full gap-3 mt-6"):

                        async def show_terrestrial_about():
                            with ui.dialog() as dialog, ui.card().classes(
                                "p-6 max-w-2xl"
                            ):
                                ui.markdown(terrestrial_about_md)
                                ui.button("Close", on_click=dialog.close).classes(
                                    "bmd-btn mt-4"
                                )
                            dialog.open()

                        ui.button(
                            "About",
                            on_click=show_terrestrial_about,
                        ).props(
                            "outline"
                        ).classes("ecosystem-action-btn flex-1").style(
                            "background: rgba(46, 204, 113, 0.05); "
                            "border: 2px solid rgba(46, 204, 113, 0.3); "
                            "color: #1A9F53;"
                        )

                        ui.button(
                            "Select",
                            on_click=lambda: ui.navigate.to("/create/terrestrial"),
                        ).classes("bmd-btn ecosystem-action-btn flex-1").props(
                            "icon=arrow_forward"
                        )

            with ui.card().classes("ecosystem-card disabled p-8 flex-1 min-w-80"):
                with ui.column().classes("w-full items-center gap-4"):
                    ui.icon("water").classes("ecosystem-icon")
                    ui.label("Freshwater").classes("text-2xl font-bold text-gray-500")
                    ui.label("Rivers, lakes, wetlands, and aquatic habitats").classes(
                        "text-sm text-gray-500 text-center"
                    )
                    ui.badge("COMING SOON").props("color=grey").classes("mt-2")

                    with ui.row().classes("w-full gap-3 mt-6"):

                        async def show_freshwater_about():
                            with ui.dialog() as dialog, ui.card().classes(
                                "p-6 max-w-2xl"
                            ):
                                ui.markdown(freshwater_about_md)
                                ui.button("Close", on_click=dialog.close).classes(
                                    "bmd-btn mt-4"
                                )
                            dialog.open()

                        ui.button(
                            "About",
                            on_click=show_freshwater_about,
                        ).props(
                            "outline"
                        ).classes("ecosystem-action-btn flex-1").style(
                            "background: rgba(156, 163, 175, 0.05); "
                            "border: 2px solid rgba(156, 163, 175, 0.3); "
                            "color: #6B7280;"
                        )

                        ui.button(
                            "Select",
                        ).classes("ecosystem-action-btn flex-1").props(
                            "disable"
                        ).style("background: #E5E7EB; color: #9CA3AF;")

    create_footer()
