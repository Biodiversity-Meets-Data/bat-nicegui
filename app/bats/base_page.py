"""Base class for BAT create-workflow pages.

Every BAT presents the same two-column form: a "Workflow Parameters" card on the
left and the shared map/geometry selector on the right. This base owns
everything common to all BATs -- the page skeleton, the name/description inputs,
the area selector, the submit flow, and route registration -- and delegates only
the BAT-specific parameter widgets and their collection to subclasses.

A subclass must:
* Set the `BAT` class attribute.
* Implement the abstract methods.
* call `Subclass.register()` at module import time to register its route.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from fastapi.responses import RedirectResponse
from nicegui import Client, ui

from bats.map_widget import MapGeometry, MapWidget
from bats.registry import Bat
from bats.workflow import (
    BatSpecificParameters,
    WorkflowValidationError,
    build_workflow_payload,
    submit_workflow,
)
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import (
    optional_textarea_input,
    page_title,
    required_label,
    required_text_input,
)


# Placeholder shown in the "Analysis Area" field until the user draws an area.
NO_GEOMETRY_MSG = "WKT: None - Draw on map ->"


class BasePage(ABC):
    """Shared structure and behaviour for BAT user-input pages.

    Instantiated once per client (inside the page handler) so each visit gets
    its own widgets.
    """

    BAT: ClassVar[Bat]

    def __init__(self) -> None:
        self.map = MapWidget(on_change=self.update_geometry)
        self.build_page()

    # ------------------------- Page Construction --------------------------- #

    def build_page(self) -> None:
        """Main method that builds the entire page for the BAT."""

        with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-6"):
            page_title("Create New Workflow")

            # Add two columns with user-input widgets.
            with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap"):
                with ui.card().classes("bmd-card p-6 flex-1 min-w-80"):
                    # Add shared and BAT-specific user inputs.
                    self.add_shared_parameters()
                    self.add_specific_parameters()

                    # Add button to submit workflow.
                    ui.button("Submit Workflow", on_click=self.on_submit).classes(
                        "w-full bmd-btn text-lg py-3 mt-6"
                    ).props("icon=send")

                # Add "Analysis Area" selection widget.
                self.map.build_widget()

    def add_shared_parameters(self) -> None:
        """Add parameters (user-input widgets) common to all BAT pages."""

        # Add a title to the user-input section.
        ui.label("Workflow Parameters").classes("text-xl font-semibold text-gray-800")

        # Workflow name and description inputs.
        self.name_input = required_text_input(
            label="Workflow Name", placeholder="e.g. Alpine Species Survey"
        )
        self.desc_input = optional_textarea_input(
            label="Description", placeholder="Describe your analysis..."
        )

        # Workflow analysis extent. The label is updated whenever the user
        # draws or clears an area on the map.
        with ui.column().classes("w-full gap-1 mt-3"):
            required_label("Analysis Area")
            self.area_label = ui.label(NO_GEOMETRY_MSG).classes(
                "text-sm text-gray-500 p-3 bg-gray-50 rounded-lg"
            )

    def update_geometry(self, geometry: MapGeometry | None) -> None:
        """Updates the page's "Analysis Area" user input with the area drawn
        by the user in the map widget associated to the page.

        This method is passed to the map widget and called by the map widget
        whenever the user draws/clears an area on the map (callback function).
        """
        self.area_label.text = f"WKT: {geometry.wkt}" if geometry else NO_GEOMETRY_MSG

    @abstractmethod
    def add_specific_parameters(self) -> None:
        """Add the BAT-specific parameters (user-input widgets) to the page."""

    # ----------------------- Workflow Submission --------------------------- #

    @abstractmethod
    def get_specific_parameters(self) -> BatSpecificParameters:
        """Collect BAT-specific user inputs."""

    def species_name(self) -> str | None:
        """Selected species, for BATs with a species input; `None` otherwise."""
        return None

    def requires_species(self) -> bool:
        """Whether the user must select a species for this BAT."""
        return False

    async def on_submit(self) -> None:
        """Validate the user inputs, then submit the workflow."""
        try:
            payload = build_workflow_payload(
                name=self.name_input.value,
                description=self.desc_input.value or "",
                ecosystem_type=self.BAT.category,
                bat_specific_parameters=self.get_specific_parameters(),
                geometry=self.map.geometry,
                species_name=self.species_name(),
                require_species=self.requires_species(),
            )
        except WorkflowValidationError as exc:
            ui.notify(str(exc), type="warning")
            return
        await submit_workflow(payload)

    # ---------------------- Page Route registration ------------------------ #

    @classmethod
    def register(cls) -> None:
        """Register the BAT page route. Must be called once, when a BAT module
        is imported.
        """

        @ui.page(cls.BAT.route)
        async def _render_page(client: Client) -> RedirectResponse | None:
            """Builder function (request handler) that NiceGUI associates with
            the URL path of the page. Each time the page is visited, this
            function runs and rebuilds the page.
            """

            # BAT workflow pages are only accessible to authenticated users.
            if not check_auth():
                return RedirectResponse("/login")

            # Add base page styling (theme).
            apply_bmd_theme()
            # Build the page by creating a new instance of the class.
            page = cls()

            # Wait for the browser's websocket connection before running
            # client-side JS code to render the map widget.
            await client.connected()
            page.map.initialize_map_widget()
            return None
