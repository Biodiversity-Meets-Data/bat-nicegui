"""Workflow results page."""

import ast
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi.responses import RedirectResponse
from nicegui import app, ui

from config import LOCAL_API_BASE_URL
from database import get_workflow_by_id
from bats.map_widget import add_readonly_aoi_map
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import card_header, page_title
from workflow_artifacts import StoredWorkflowArtifacts, load_workflow_artifacts


class WorkflowResultsPage:
    """Page displaying the results of a single completed workflow.

    Instantiated once per visit (inside the page handler), after the user has
    been authenticated and the workflow fetched and its results parsed.
    """

    ROUTE = "/results/{workflow_id}"

    def __init__(
        self,
        workflow_id: str,
        workflow: dict[str, Any],
        results: Any,
        artifacts: StoredWorkflowArtifacts,
    ) -> None:
        self.workflow_id = workflow_id
        self.workflow = workflow
        self.results = results
        self.artifacts = artifacts
        self.artifact_section: Any = None
        self.artifact_status_label: Any = None
        self.artifact_action_button: Any = None
        self.artifact_spinner: Any = None
        self.artifact_poll_timer: Any = None
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
                with ui.column().classes("w-full gap-6") as artifact_section:
                    self.artifact_section = artifact_section
                    self.render_artifact_sections()

                if isinstance(self.results, dict) and "summary" in self.results:
                    self.add_summary_card()
                    self.add_model_performance_card()
                    with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
                        self.add_top_species_card()
                        self.add_env_variables_card()
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
        """Build the generic workflow-details card."""

        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Workflow Details")
            with ui.row().classes("w-full items-start gap-6 flex-wrap lg:flex-nowrap"):
                with ui.column().classes("flex-1 min-w-0 gap-4"):
                    with ui.row().classes("gap-8 flex-wrap"):
                        with ui.column().classes("gap-1"):
                            ui.label("Workflow ID").classes("text-xs text-gray-500")
                            ui.label(self.workflow_id).classes(
                                "font-mono text-sm break-all"
                            )
                        with ui.column().classes("gap-1"):
                            ui.label("BAT").classes("text-xs text-gray-500")
                            ui.label(self.workflow.get("bat_name") or "-").classes(
                                "font-medium"
                            )
                        with ui.column().classes("gap-1"):
                            ui.label("Realm").classes("text-xs text-gray-500")
                            ui.label(
                                self.workflow.get("ecosystem_type") or "-"
                            ).classes("font-medium")
                        with ui.column().classes("gap-1"):
                            ui.label("Created").classes("text-xs text-gray-500")
                            ui.label(
                                self.workflow["created_at"][:19]
                                if self.workflow["created_at"]
                                else "N/A"
                            ).classes("font-medium")
                        with ui.column().classes("gap-1"):
                            ui.label("Completed").classes("text-xs text-gray-500")
                            ui.label(
                                self.workflow["completed_at"][:19]
                                if self.workflow.get("completed_at")
                                else "-"
                            ).classes("font-medium")
                        with ui.column().classes("gap-1"):
                            ui.label("Duration").classes("text-xs text-gray-500")
                            ui.label(self._workflow_duration()).classes(
                                "font-mono font-medium"
                            )
                        with ui.column().classes("gap-1"):
                            ui.label("Status").classes("text-xs text-gray-500")
                            status = str(
                                self.workflow.get("status") or "unknown"
                            ).upper()
                            status_color = (
                                "green"
                                if status in {"COMPLETED", "SUCCEEDED"}
                                else "red"
                                if status in {"FAILED", "ERROR"}
                                else "blue"
                            )
                            ui.badge(status).props(f"color={status_color}")
                    if self.workflow.get("description"):
                        ui.label("Description").classes("text-xs text-gray-500")
                        ui.label(str(self.workflow["description"])).classes(
                            "text-gray-700 whitespace-pre-wrap"
                        )
                with ui.column().classes("w-full lg:w-80 lg:shrink-0 gap-2"):
                    ui.label("Area of Interest").classes("text-xs text-gray-500")
                    add_readonly_aoi_map(self.workflow.get("geometry_wkt"))

    def _workflow_duration(self) -> str:
        """Format the completed workflow duration as days, hours, minutes, seconds."""

        created_at = self.workflow.get("created_at")
        completed_at = self.workflow.get("completed_at")
        if not created_at or not completed_at:
            return "-"
        try:
            start = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(completed_at).replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            total_seconds = max(0, int((end - start).total_seconds()))
        except ValueError:
            return "-"

        days, remainder = divmod(total_seconds, 24 * 60 * 60)
        hours, remainder = divmod(remainder, 60 * 60)
        minutes, seconds = divmod(remainder, 60)
        return f"{days:02d}:{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _metadata_entities(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Index RO-Crate graph entities by identifier."""

        graph = metadata.get("@graph", [])
        if not isinstance(graph, list):
            return {}
        return {
            entity["@id"]: entity
            for entity in graph
            if isinstance(entity, dict) and isinstance(entity.get("@id"), str)
        }

    def add_rocrate_card(self) -> None:
        """Display provenance and output information from RO-Crate metadata."""

        metadata = self.artifacts.metadata
        if not metadata:
            return

        entities = self._metadata_entities(metadata)
        root = entities.get("./", {})
        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Workflow Provenance")
            if root.get("description"):
                ui.label(str(root["description"])).classes("text-gray-600 mb-4")
            with ui.row().classes("gap-8 flex-wrap"):
                self._add_metadata_value("Author", root.get("author"), entities)
                self._add_metadata_value("License", root.get("license"), entities)
                self._add_metadata_value("Created", root.get("dateCreated"))
                self._add_metadata_value("Published", root.get("datePublished"))
                self._add_metadata_value("Modified", root.get("dateModified"))
                doi = self._metadata_doi(root.get("author"), entities)
                if doi:
                    with ui.column().classes("gap-1"):
                        ui.label("Cite as").classes("text-xs text-gray-500")
                        ui.link(doi, doi).classes("text-sm break-all")

            keywords = root.get("keywords", [])
            if isinstance(keywords, list) and keywords:
                ui.label("Keywords").classes("text-xs text-gray-500 mt-4")
                with ui.row().classes("gap-2 flex-wrap"):
                    for keyword in keywords:
                        ui.badge(str(keyword)).props("color=teal")

            conforms_to = root.get("conformsTo", [])
            if isinstance(conforms_to, list) and conforms_to:
                ui.label("Conforms to").classes("text-xs text-gray-500 mt-4")
                with ui.column().classes("gap-1"):
                    for item in conforms_to:
                        identifier = self._metadata_identifier(item)
                        if identifier:
                            ui.link(identifier, identifier).props(
                                "target=_blank"
                            ).classes("font-mono text-xs break-all")

            parts = root.get("hasPart", [])
            if isinstance(parts, list) and parts:
                ui.label("Workflow outputs").classes("text-xs text-gray-500 mt-4")
                with ui.column().classes("w-full max-h-64 overflow-y-auto gap-1 pr-2"):
                    for part in parts:
                        identifier = self._metadata_identifier(part)
                        entity = entities.get(identifier or "", {})
                        output_name = str(entity.get("name") or identifier or "Unknown")
                        output_type = str(entity.get("@type") or "File")
                        ui.label(f"{output_name} ({output_type})").classes(
                            "font-mono text-xs break-all"
                        )

    def render_artifact_sections(self) -> None:
        """Render the current artifact state inside the reactive section."""

        if self.artifact_section is None:
            return
        self.artifact_section.clear()
        with self.artifact_section:
            self.add_rocrate_card()
            self.add_logs_card()
            self.add_artifact_status_card()

    @staticmethod
    def _metadata_identifier(value: Any) -> str | None:
        """Read an RO-Crate identifier from a string or reference object."""

        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("@id"), str):
            return str(value["@id"])
        return None

    @classmethod
    def _metadata_doi(
        cls, value: Any, entities: dict[str, dict[str, Any]]
    ) -> str | None:
        """Find a DOI in an RO-Crate author reference."""

        identifier = cls._metadata_identifier(value)
        candidates: list[str] = []
        if identifier:
            candidates.append(identifier)
            author_entity = entities.get(identifier, {})
            same_as = cls._metadata_identifier(author_entity.get("sameAs"))
            if same_as:
                candidates.append(same_as)
        for candidate in candidates:
            if candidate.startswith("https://doi.org/"):
                return candidate
        return None

    def _add_metadata_value(
        self,
        label: str,
        value: Any,
        entities: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Render one compact RO-Crate metadata field."""

        if entities is not None:
            identifier = self._metadata_identifier(value)
            if identifier and identifier in entities:
                entity = entities[identifier]
                value = entity.get("name") or identifier
            else:
                value = identifier
        if value is None:
            return
        with ui.column().classes("gap-1"):
            ui.label(label).classes("text-xs text-gray-500")
            ui.label(str(value)).classes("text-sm break-all")

    def add_logs_card(self) -> None:
        """Display each persisted workflow-step log in an expandable panel."""

        if not self.artifacts.logs:
            return
        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Workflow Logs")
            for log in self.artifacts.logs:
                with ui.expansion(log.name, icon="article").classes("w-full"):
                    try:
                        content = log.path.read_text(encoding="utf-8", errors="replace")
                    except OSError as exc:
                        content = f"Unable to read log: {exc}"
                    ui.code(content).classes(
                        "w-full max-h-96 overflow-auto bg-black text-white p-4 rounded font-mono"
                    ).style("background-color: #000; color: #fff")

    def add_artifact_status_card(self) -> None:
        """Display extraction progress and offer a retry when extraction failed."""

        if self.artifacts.metadata or self.artifacts.logs:
            return
        artifact_status = self.workflow.get("artifact_status") or "pending"
        if artifact_status == "ready":
            return
        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Workflow files")
            with ui.row().classes("items-center gap-2"):
                self.artifact_spinner = ui.spinner(
                    "dots", size="1.5em", color="primary"
                )
                self.artifact_spinner.set_visibility(False)
                if artifact_status == "failed":
                    self.artifact_status_label = ui.label(
                        self.workflow.get("artifact_error")
                        or "The workflow files could not be prepared."
                    ).classes("text-red-600")
                else:
                    self.artifact_status_label = ui.label(
                        "Preparing workflow metadata and logs..."
                    ).classes("text-gray-500")
            self.artifact_action_button = (
                ui.button(
                    "Retry" if artifact_status == "failed" else "Prepare files now",
                    on_click=self.retry_artifact_extraction,
                )
                .props("icon=refresh")
                .classes("bmd-btn mt-3")
            )

    async def retry_artifact_extraction(self) -> None:
        """Queue extraction again and refresh the results page."""

        token = app.storage.user.get("token")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{LOCAL_API_BASE_URL}/api/workflows/{self.workflow_id}/artifacts/retry",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if response.status_code >= 300:
                ui.notify(f"Retry failed: {response.text}", type="negative")
                return
        except httpx.HTTPError as exc:
            ui.notify(f"Retry failed: {exc}", type="negative")
            return
        if self.artifact_status_label is not None:
            self.artifact_status_label.set_text(
                "Preparing workflow metadata and logs..."
            )
        if self.artifact_spinner is not None:
            self.artifact_spinner.set_visibility(True)
        if self.artifact_action_button is not None:
            self.artifact_action_button.disable()
        if self.artifact_poll_timer is None or not self.artifact_poll_timer.active:
            self.artifact_poll_timer = ui.timer(
                2.0, self.poll_artifact_status, immediate=False
            )
        ui.notify("Workflow files are being prepared", type="positive")

    async def poll_artifact_status(self) -> None:
        """Refresh the artifact section when background extraction completes."""

        workflow = get_workflow_by_id(self.workflow_id)
        if not workflow:
            if self.artifact_poll_timer is not None:
                self.artifact_poll_timer.cancel()
            return

        artifact_status = workflow.get("artifact_status") or "pending"
        if artifact_status not in {"ready", "failed"}:
            return

        if self.artifact_poll_timer is not None:
            self.artifact_poll_timer.cancel()
        self.workflow = workflow
        try:
            self.artifacts = load_workflow_artifacts(self.workflow_id)
        except (OSError, ValueError, TypeError):
            self.artifacts = StoredWorkflowArtifacts(None, ())
        self.render_artifact_sections()
        if artifact_status == "ready":
            ui.notify("Workflow metadata and logs are ready", type="positive")
        else:
            ui.notify(
                "Workflow metadata and logs could not be prepared", type="negative"
            )

    def add_summary_card(self) -> None:
        """Build the summary card (species / occurrences / analysis area)."""

        with ui.card().classes("bmd-card p-6 w-full"):
            card_header("Summary")
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
            card_header("Model Performance Metrics")
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
            card_header("Top Species by Habitat Suitability")
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
            card_header("Environmental Variable Importance")
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

            try:
                artifacts = load_workflow_artifacts(workflow_id)
            except (OSError, ValueError, TypeError):
                artifacts = StoredWorkflowArtifacts(None, ())

            # Build the page by creating a new instance of the class.
            WorkflowResultsPage(workflow_id, workflow, results, artifacts)
            return None


WorkflowResultsPage.register()
