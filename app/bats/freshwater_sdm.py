"""Freshwater SDM create workflow page."""

from dataclasses import dataclass
from nicegui import ui

from bats.base_page import BasePage
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters, WorkflowValidationError
from ui_widgets import required_label


# have commented out parameters that we do not have implemented yet into our model
@dataclass(frozen=True, slots=True, kw_only=True)
class FreshwaterSdmParameters(BatSpecificParameters):
    """BAT-specific workflow parameters for the freshwater SDM BAT."""

    directive_types: list[str]
    time_period: str  ##model currently only set up to look at 1 time period at a time
    #   min_observations: float | None
    #   confidence_threshold: float | None
    #   include_historical: bool
    #   generate_report: bool

    def validate_input(self) -> None:
        if not self.directive_types:
            raise WorkflowValidationError("Please choose an EU directive")
        if not self.time_period:
            raise WorkflowValidationError("Please select a time period")

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"climate_period": self.time_period}

    def to_parameter_metadata(self) -> dict[str, object]:
        return {"directive_types": self.directive_types}


class FreshwaterSdmPage(BasePage):
    """Freshwater SDM create-workflow page."""

    BAT = get_bat_by_name("freshwater_sdm")

    def __init__(self) -> None:
        self.time_period = [
            "1981-2010",
            #   "2011-2040",
            "2041-2070",
            "2071-2100",
        ]
        super().__init__()

    # ------------------------- Page Construction --------------------------- #

    def add_species_directive_parameters(self) -> None:
        """Add the directive filters used by the shared species selector."""
        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Choose EU Directive")
            with ui.row().classes("w-full gap-4"):
                self.invasive_cb = (
                    ui.checkbox("Invasive Species Regulations", value=False)
                    .props("checked-icon=check_box")
                    .classes("flex-1")
                )
                self.habitat_cb = (
                    ui.checkbox("Habitats", value=False)
                    .props("checked-icon=check_box")
                    .classes("flex-1")
                )
                self.bird_cb = (
                    ui.checkbox("Bird", value=False)
                    .props("checked-icon=check_box")
                    .classes("flex-1")
                )
        self.invasive_cb.on_value_change(
            lambda _: self.update_species_options(tuple(self.selected_directives()))
        )
        self.habitat_cb.on_value_change(
            lambda _: self.update_species_options(tuple(self.selected_directives()))
        )
        self.bird_cb.on_value_change(
            lambda _: self.update_species_options(tuple(self.selected_directives()))
        )

    def add_specific_parameters(self) -> None:
        """Add the BAT-specific parameters (user-input widgets) to the page."""

        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Time Period")
            self.time_period_select = (
                ui.select(
                    options=self.time_period,
                    value=None,
                )
                .props("outlined")
                .classes("w-full")
            )

        #  ui.label("Additional Parameters").classes(
        #      "text-sm font-semibold text-gray-600 mt-4 mb-2"
        #  )

        #  with ui.row().classes("w-full gap-4 mb-4"):
        #      self.min_obs = (
        #          ui.number("Min Observations", value=10)
        #          .props("outlined")
        #          .classes("flex-1")
        #      )
        #      self.confidence = ui.slider(min=0, max=100, value=80).classes("flex-1")
        #      ui.label().bind_text_from(
        #          self.confidence, "value", lambda v: f"Confidence: {v}%"
        #      )

        #  self.include_historical = ui.checkbox("Include historical data", value=True)
        self.generate_report = ui.checkbox("Generate PDF report", value=True)

    def get_specific_parameters(self) -> FreshwaterSdmParameters:
        return FreshwaterSdmParameters(
            directive_types=self.selected_directives(),
            time_period=self.time_period_select.value or "",
            #    min_observations=self.min_obs.value,
            #    confidence_threshold=self.confidence.value,
            #    include_historical=bool(self.include_historical.value),
            #    generate_report=bool(self.generate_report.value),
        )

    def selected_directives(self) -> list[str]:
        directive_types: list[str] = []
        if self.invasive_cb.value:
            directive_types.append("invasive_species")
        if self.habitat_cb.value:
            directive_types.append("habitat")
        if self.bird_cb.value:
            directive_types.append("bird")
        return directive_types


FreshwaterSdmPage.register()
