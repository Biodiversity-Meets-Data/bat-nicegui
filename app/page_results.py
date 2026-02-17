"""Workflow results page."""

import ast

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from database import get_workflow_by_id
from ui_common import apply_bmd_theme, check_auth, create_footer


@ui.page("/results/{workflow_id}")
async def results_page(workflow_id: str):
    user_id = check_auth()
    if not user_id:
        return RedirectResponse("/login")

    apply_bmd_theme()
    ui.run_javascript("document.body.classList.remove('public-auth')")

    workflow = get_workflow_by_id(workflow_id)
    if not workflow or workflow["user_id"] != user_id:
        with ui.column().classes("w-full min-h-screen items-center justify-center"):
            ui.label("Workflow not found").classes("text-xl text-red-500")
            ui.button(
                "Back to Workflows", on_click=lambda: ui.navigate.to("/workflows")
            ).classes("bmd-btn mt-4")
        create_footer()
        return

    try:
        results = ast.literal_eval(workflow["results"]) if workflow["results"] else {}
    except Exception:
        results = {"raw": workflow["results"]}

    download_url = f"/api/workflows/{workflow_id}/download"
    token = app.storage.user.get("token")
    if token:
        download_url = f"{download_url}?token={token}"

    with ui.column().classes("w-full min-h-screen"):
        with ui.row().classes("w-full bg-white shadow-sm p-4 items-center gap-4"):
            ui.button(
                icon="arrow_back", on_click=lambda: ui.navigate.to("/workflows")
            ).props("flat round")
            with ui.column().classes("gap-0"):
                ui.label("Analysis Results").classes("text-xl font-bold").style(
                    "background: linear-gradient(135deg, #2ECC71, #0077B6); "
                    "-webkit-background-clip: text; -webkit-text-fill-color: transparent;"
                )
                ui.label(f"{workflow['name']}").classes("text-sm text-gray-500")
            ui.button(
                "Download Results",
                icon="download",
                on_click=lambda url=download_url: ui.navigate.to(url),
            ).props("flat").classes(
                "ml-auto bg-white border border-gray-200 text-orange-500 font-medium"
            )

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
            with ui.card().classes("bmd-card p-6 w-full"):
                ui.label("Workflow Details").classes(
                    "text-lg font-semibold text-gray-800 mb-4"
                )
                with ui.row().classes("gap-8 flex-wrap"):
                    with ui.column().classes("gap-1"):
                        ui.label("Workflow ID").classes("text-xs text-gray-500")
                        ui.label(workflow_id[:20] + "...").classes("font-mono text-sm")
                    with ui.column().classes("gap-1"):
                        ui.label("Species Group").classes("text-xs text-gray-500")
                        ui.label(workflow.get("species_name") or "-").classes(
                            "font-medium"
                        )
                    with ui.column().classes("gap-1"):
                        ui.label("Created").classes("text-xs text-gray-500")
                        ui.label(
                            workflow["created_at"][:19]
                            if workflow["created_at"]
                            else "N/A"
                        ).classes("font-medium")
                    with ui.column().classes("gap-1"):
                        ui.label("Status").classes("text-xs text-gray-500")
                        ui.badge("COMPLETED").props("color=green")

            if isinstance(results, dict) and "summary" in results:
                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Summary").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    with ui.row().classes("gap-8 justify-around"):
                        with ui.column().classes("items-center p-4"):
                            ui.label(str(results["summary"]["total_species"])).classes(
                                "text-4xl font-bold text-green-600"
                            )
                            ui.label("Species Detected").classes(
                                "text-sm text-gray-600"
                            )
                        with ui.column().classes("items-center p-4"):
                            ui.label(
                                f'{results["summary"]["total_occurrences"]:,}'
                            ).classes("text-4xl font-bold text-teal-600")
                            ui.label("Total Occurrences").classes(
                                "text-sm text-gray-600"
                            )
                        with ui.column().classes("items-center p-4"):
                            ui.label(f'{results["summary"]["area_km2"]:,.0f}').classes(
                                "text-4xl font-bold text-blue-600"
                            )
                            ui.label("Analysis Area (km²)").classes(
                                "text-sm text-gray-600"
                            )

                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Model Performance Metrics").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    with ui.row().classes("gap-6 justify-around"):
                        perf = results["model_performance"]
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['auc_score']:.3f}").classes(
                                "text-3xl font-bold text-green-600"
                            )
                            ui.label("AUC Score").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["auc_score"], show_value=False
                            ).classes("w-24").props("color=green")
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['tss_score']:.3f}").classes(
                                "text-3xl font-bold text-teal-600"
                            )
                            ui.label("TSS Score").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["tss_score"], show_value=False
                            ).classes("w-24").props("color=teal")
                        with ui.column().classes("items-center p-4"):
                            ui.label(f"{perf['kappa']:.3f}").classes(
                                "text-3xl font-bold text-blue-600"
                            )
                            ui.label("Kappa").classes("text-sm text-gray-600")
                            ui.linear_progress(
                                value=perf["kappa"], show_value=False
                            ).classes("w-24").props("color=blue")

                with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
                    with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                        ui.label("Top Species by Habitat Suitability").classes(
                            "text-lg font-semibold text-gray-800 mb-4"
                        )
                        for i, species in enumerate(results.get("top_species", [])):
                            with ui.row().classes(
                                "w-full items-center justify-between py-3 border-b border-gray-100"
                            ):
                                with ui.row().classes("items-center gap-3"):
                                    ui.label(f"{i+1}").classes(
                                        "w-6 h-6 rounded-full bg-green-100 text-green-700 text-center text-sm font-bold"
                                    )
                                    with ui.column().classes("gap-0"):
                                        ui.label(species["name"]).classes(
                                            "font-medium italic"
                                        )
                                        ui.label(
                                            f'{species["occurrences"]} occurrences'
                                        ).classes("text-xs text-gray-500")
                                with ui.column().classes("items-end"):
                                    ui.label(
                                        f'{species["habitat_suitability"]:.0%}'
                                    ).classes("text-lg font-bold text-green-600")
                                    ui.label("suitability").classes(
                                        "text-xs text-gray-500"
                                    )

                    with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                        ui.label("Environmental Variable Importance").classes(
                            "text-lg font-semibold text-gray-800 mb-4"
                        )
                        for var_name, var_data in results.get(
                            "environmental_variables", {}
                        ).items():
                            with ui.column().classes("w-full py-2"):
                                with ui.row().classes("w-full justify-between mb-1"):
                                    ui.label(
                                        var_name.replace("_", " ")
                                        .replace("bio1 ", "Mean Temp ")
                                        .replace("bio12 ", "Annual Precip ")
                                        .title()
                                    ).classes("text-sm font-medium")
                                    ui.label(
                                        f'{var_data["contribution_pct"]}%'
                                    ).classes("text-sm font-bold text-teal-600")
                                ui.linear_progress(
                                    value=var_data["contribution_pct"] / 100,
                                    show_value=False,
                                ).classes("w-full").props("color=teal size=10px")
            else:
                with ui.card().classes("bmd-card p-6 w-full"):
                    ui.label("Raw Results").classes(
                        "text-lg font-semibold text-gray-800 mb-4"
                    )
                    ui.code(str(results)).classes("w-full")

            ui.button(
                "<- Back to Workflows", on_click=lambda: ui.navigate.to("/workflows")
            ).classes("bmd-btn mt-4")
    create_footer()
