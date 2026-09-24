"""Terrestrial SDM create workflow page."""

from dataclasses import dataclass
from typing import Any

from nicegui import ui

from bats.base_page import BasePage
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters, WorkflowValidationError
from ui_widgets import required_label


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialSdmParameters(BatSpecificParameters):
    """BAT-specific workflow parameters for the terrestrial SDM BAT."""

    directive_types: list[str]
    time_periods: list[str]

    def validate_input(self) -> None:
        if not self.directive_types:
            raise WorkflowValidationError("Please choose an EU directive")
        if not self.time_periods:
            raise WorkflowValidationError("Please select a time period")

    def to_api_parameters(self) -> dict[str, Any]:
        return {
            "time_period": ";".join(self.time_periods),
            "directive_types": self.directive_types,
        }

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"climate_periods": ";".join(self.time_periods)}


class TerrestrialSdmPage(BasePage):
    """Terrestrial SDM create-workflow page."""

    BAT = get_bat_by_name("terrestrial_sdm")

    def __init__(self) -> None:
        self.time_periods = [
            "1981-2010",
            "2011-2040",
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
            self.time_period_checks = [
                ui.checkbox(period, value=False).classes("w-full")
                for period in self.time_periods
            ]

    def get_specific_parameters(self) -> TerrestrialSdmParameters:
        return TerrestrialSdmParameters(
            directive_types=self.selected_directives(),
            time_periods=self.selected_time_periods(),
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

    def selected_time_periods(self) -> list[str]:
        return [
            period
            for period, checkbox in zip(self.time_periods, self.time_period_checks)
            if checkbox.value
        ]


TerrestrialSdmPage.register()
