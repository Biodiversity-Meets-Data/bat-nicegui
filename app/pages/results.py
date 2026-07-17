"""Workflow results page."""

import ast
from typing import Any

from fastapi.responses import RedirectResponse
from nicegui import app, ui

from database import get_workflow_by_id
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import page_title


class WorkflowResultsPage:
    """Page displaying the results of a single completed workflow.

    Instantiated once per visit (inside the page handler), after the user has
    been authenticated and the workflow fetched and its results parsed.
    """

    ROUTE = "/results/{workflow_id}"

    def __init__(
        self, workflow_id: str, workflow: dict[str, Any], results: Any
    ) -> None:
        self.workflow_id = workflow_id
        self.workflow = workflow
        self.results = results
        # Presentation detail: the download URL carries the auth token so the
        # browser can fetch the protected endpoint directly.
        self.download_url = f"/api/workflows/{workflow_id}/download"
        token = app.storage.user.get("token")
        if token:
            self.download_url = f"{self.download_url}?token={token}"
        self.build_page()

    # ------------------------- Page construction --------------------------- #

    def build_page(self) -> None:
        """Build the page: header bar plus the results detail sections."""

        with ui.column().classes("w-full min-h-screen"):
            self.add_header()

            with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
                self.add_workflow_details_card()

                if isinstance(self.results, dict) and "summary" in self.results:
                    self.add_summary_card()
                    self.add_model_performance_card()
                    with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
                        self.add_top_species_card()
                        self.add_env_variables_card()
                else:
                    self.add_raw_results_card()

                ui.button(
                    "<- Back to Workflows",
                    on_click=lambda: ui.navigate.to("/workflows"),
                ).classes("bmd-btn mt-4")

    def add_header(self) -> None:
        """Build the top header bar: back button, title, and download button."""

        with ui.row().classes("w-full bg-white shadow-sm p-4 items-center gap-4"):
            ui.button(
                icon="arrow_back", on_click=lambda: ui.navigate.to("/workflows")
            ).props("flat round")
            with ui.column().classes("gap-0"):
                page_title("Analysis Results")
                ui.label(f"{self.workflow['name']}").classes("text-sm text-gray-500")
            ui.button(
                "Download Results",
                icon="download",
                on_click=lambda: ui.navigate.to(self.download_url),
            ).props("flat").classes(
                "ml-auto bg-white border border-gray-200 text-orange-500 font-medium"
            )

    def add_workflow_details_card(self) -> None:
        """Build the workflow-details card (id, species, created, status)."""

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Workflow Details").classes(
                "text-lg font-semibold text-gray-800 mb-4"
            )
            with ui.row().classes("gap-8 flex-wrap"):
                with ui.column().classes("gap-1"):
                    ui.label("Workflow ID").classes("text-xs text-gray-500")
                    ui.label(self.workflow_id[:20] + "...").classes("font-mono text-sm")
                with ui.column().classes("gap-1"):
                    ui.label("Species Group").classes("text-xs text-gray-500")
                    ui.label(self.workflow.get("species_name") or "-").classes(
                        "font-medium"
                    )
                with ui.column().classes("gap-1"):
                    ui.label("Created").classes("text-xs text-gray-500")
                    ui.label(
                        self.workflow["created_at"][:19]
                        if self.workflow["created_at"]
                        else "N/A"
                    ).classes("font-medium")
                with ui.column().classes("gap-1"):
                    ui.label("Status").classes("text-xs text-gray-500")
                    ui.badge("COMPLETED").props("color=green")

    def add_summary_card(self) -> None:
        """Build the summary card (species / occurrences / analysis area)."""

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Summary").classes("text-lg font-semibold text-gray-800 mb-4")
            with ui.row().classes("gap-8 justify-around"):
                with ui.column().classes("items-center p-4"):
                    ui.label(str(self.results["summary"]["total_species"])).classes(
                        "text-4xl font-bold text-green-600"
                    )
                    ui.label("Species Detected").classes("text-sm text-gray-600")
                with ui.column().classes("items-center p-4"):
                    ui.label(
                        f"{self.results['summary']['total_occurrences']:,}"
                    ).classes("text-4xl font-bold text-teal-600")
                    ui.label("Total Occurrences").classes("text-sm text-gray-600")
                with ui.column().classes("items-center p-4"):
                    ui.label(f"{self.results['summary']['area_km2']:,.0f}").classes(
                        "text-4xl font-bold text-blue-600"
                    )
                    ui.label("Analysis Area (km²)").classes("text-sm text-gray-600")

    def add_model_performance_card(self) -> None:
        """Build the model-performance card (AUC / TSS / Kappa)."""

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Model Performance Metrics").classes(
                "text-lg font-semibold text-gray-800 mb-4"
            )
            with ui.row().classes("gap-6 justify-around"):
                perf = self.results["model_performance"]
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
                    ui.linear_progress(value=perf["kappa"], show_value=False).classes(
                        "w-24"
                    ).props("color=blue")

    def add_top_species_card(self) -> None:
        """Build the ranked top-species-by-habitat-suitability card."""

        with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
            ui.label("Top Species by Habitat Suitability").classes(
                "text-lg font-semibold text-gray-800 mb-4"
            )
            for i, species in enumerate(self.results.get("top_species", [])):
                with ui.row().classes(
                    "w-full items-center justify-between py-3 border-b border-gray-100"
                ):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(f"{i + 1}").classes(
                            "w-6 h-6 rounded-full bg-green-100 text-green-700 text-center text-sm font-bold"
                        )
                        with ui.column().classes("gap-0"):
                            ui.label(species["name"]).classes("font-medium italic")
                            ui.label(f"{species['occurrences']} occurrences").classes(
                                "text-xs text-gray-500"
                            )
                    with ui.column().classes("items-end"):
                        ui.label(f"{species['habitat_suitability']:.0%}").classes(
                            "text-lg font-bold text-green-600"
                        )
                        ui.label("suitability").classes("text-xs text-gray-500")

    def add_env_variables_card(self) -> None:
        """Build the environmental-variable importance card."""

        with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
            ui.label("Environmental Variable Importance").classes(
                "text-lg font-semibold text-gray-800 mb-4"
            )
            for var_name, var_data in self.results.get(
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
                        ui.label(f"{var_data['contribution_pct']}%").classes(
                            "text-sm font-bold text-teal-600"
                        )
                    ui.linear_progress(
                        value=var_data["contribution_pct"] / 100,
                        show_value=False,
                    ).classes("w-full").props("color=teal size=10px")

    def add_raw_results_card(self) -> None:
        """Build the fallback card shown when results lack a summary."""

        with ui.card().classes("bmd-card p-6 w-full"):
            ui.label("Raw Results").classes("text-lg font-semibold text-gray-800 mb-4")
            ui.code(str(self.results)).classes("w-full")

    # ---------------------- Page Route registration ------------------------ #

    @classmethod
    def register(cls) -> None:
        """Register the page's route.

        Add <cls>.register() at the end of the page's module so that the
        method gets called when the module is imported.
        """

        @ui.page(cls.ROUTE)
        async def _render_page(workflow_id: str) -> RedirectResponse | None:
            # Page is only accessible to authenticated users.
            user_id = check_auth()
            if not user_id:
                return RedirectResponse("/login")

            # Add base page styling (theme).
            apply_bmd_theme()

            # Fetch the workflow and guard access: it must exist and belong to
            # the current user.
            workflow = get_workflow_by_id(workflow_id)
            if not workflow or workflow["user_id"] != user_id:
                with ui.column().classes(
                    "w-full min-h-screen items-center justify-center"
                ):
                    ui.label("Workflow not found").classes("text-xl text-red-500")
                    ui.button(
                        "Back to Workflows",
                        on_click=lambda: ui.navigate.to("/workflows"),
                    ).classes("bmd-btn mt-4")
                return None

            # Parse the stored results (falling back to raw text on error).
            try:
                results = (
                    ast.literal_eval(workflow["results"]) if workflow["results"] else {}
                )
            except Exception:
                results = {"raw": workflow["results"]}

            # Build the page by creating a new instance of the class.
            WorkflowResultsPage(workflow_id, workflow, results)
            return None


WorkflowResultsPage.register()
