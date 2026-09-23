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
import json
from typing import ClassVar

from fastapi.responses import RedirectResponse
from nicegui import Client, ui

from bats.map_widget import MapGeometry, MapWidget
from bats.registry import Bat
from species import (
    SpeciesOption,
    load_species_options,
    species_lists_for_directives,
)
from bats.workflow import (
    BatSpecificParameters,
    WorkflowValidationError,
    build_workflow_payload,
    submit_workflow,
)
from ui_common import apply_bmd_theme, check_auth
from ui_widgets import (
    card_header,
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
        self.map = MapWidget(
            on_change=self.update_geometry,
            selection_modes=self.BAT.map_selection_modes,
        )
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
                    self.add_species_directive_parameters()
                    self.add_species_selector()
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
        card_header("Workflow Parameters")

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
            with ui.row().classes("w-full items-start gap-2 p-3 bg-gray-50 rounded-lg"):
                self.area_label = (
                    ui.label(NO_GEOMETRY_MSG)
                    .classes("text-sm text-gray-500 flex-1 w-0")
                    .style(
                        "display: -webkit-box; "
                        "-webkit-box-orient: vertical; "
                        "-webkit-line-clamp: 2; "
                        "overflow: hidden; "
                        "overflow-wrap: anywhere;"
                    )
                )
                self.copy_wkt_button = ui.button(
                    icon="content_copy", on_click=self.copy_geometry_wkt
                ).props("flat dense round size=sm")
                self.copy_wkt_button.tooltip("Copy WKT")
                self.copy_wkt_button.disable()

    def update_geometry(self, geometry: MapGeometry | None) -> None:
        """Updates the page's "Analysis Area" user input with the area drawn
        by the user in the map widget associated to the page.

        This method is passed to the map widget and called by the map widget
        whenever the user draws/clears an area on the map (callback function).
        """
        self.area_label.text = f"WKT: {geometry.wkt}" if geometry else NO_GEOMETRY_MSG
        if geometry:
            self.copy_wkt_button.enable()
        else:
            self.copy_wkt_button.disable()

    def add_species_directive_parameters(self) -> None:
        """Add optional directive controls before the shared species selector."""

    def add_species_selector(self) -> None:
        """Add the shared species selector when the BAT opts into species."""
        self.species_select = None
        self._species_by_col_id: dict[str, SpeciesOption] = {}
        if not self.BAT.species_lists:
            return

        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Species List")
            self.species_select = (
                ui.select(
                    options={},
                    value=None,
                )
                .props("outlined use-input input-debounce=0 options-html clearable")
                .classes("w-full")
            )
        self.species_select.on_value_change(self.update_species_display)
        self.update_species_options(())

    def update_species_options(self, directives: tuple[str, ...]) -> None:
        """Refresh species options from the currently selected directives."""
        if self.species_select is None:
            return
        list_ids = species_lists_for_directives(directives, self.BAT.species_lists)
        options = load_species_options(list_ids)
        self._species_by_col_id = {option.col_id: option for option in options}
        self.species_select.options = {
            option.col_id: option.html_label for option in options
        }
        if self.species_select.value not in self.species_select.options:
            self.species_select.value = None
        self.species_select.update()

    def update_species_display(self, _: object | None = None) -> None:
        """Show the scientific name after a species option is selected."""
        if self.species_select is None:
            return
        selected = self._species_by_col_id.get(str(self.species_select.value))
        self.species_select.props(
            f"display-value={json.dumps(selected.scientific_name if selected else '')}"
        )
        self.species_select.update()

    async def copy_geometry_wkt(self) -> None:
        """Copy the selected analysis-area WKT to the browser clipboard."""
        geometry = self.map.geometry
        if geometry is None:
            ui.notify("Select an analysis area first", type="warning")
            return
        await ui.run_javascript(
            f"navigator.clipboard.writeText({json.dumps(geometry.wkt)});",
            timeout=5.0,
        )
        ui.notify("WKT copied to clipboard", type="positive")

    @abstractmethod
    def add_specific_parameters(self) -> None:
        """Add the BAT-specific parameters (user-input widgets) to the page."""

    # ----------------------- Workflow Submission --------------------------- #

    @abstractmethod
    def get_specific_parameters(self) -> BatSpecificParameters:
        """Collect BAT-specific user inputs."""

    def species_name(self) -> str | None:
        """Selected species, for BATs with a species input; `None` otherwise."""
        option = self._selected_species()
        return option.scientific_name if option else None

    def species_col_id(self) -> str | None:
        """Selected Catalogue of Life identifier, if this BAT has a species."""
        option = self._selected_species()
        return option.col_id if option else None

    def _selected_species(self) -> SpeciesOption | None:
        if self.species_select is None or self.species_select.value is None:
            return None
        return self._species_by_col_id.get(str(self.species_select.value))

    def requires_species(self) -> bool:
        """Whether the user must select a species for this BAT."""
        return bool(self.BAT.species_lists)

    async def on_submit(self) -> None:
        """Validate the user inputs, then submit the workflow."""
        try:
            payload = build_workflow_payload(
                name=(self.name_input.value or "").strip(),
                description=(self.desc_input.value or "").strip(),
                bat_name=self.BAT.name,
                ecosystem_type=self.BAT.category,
                bat_specific_parameters=self.get_specific_parameters(),
                geometry=self.map.geometry,
                species_name=self.species_name(),
                species_col_id=self.species_col_id(),
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
