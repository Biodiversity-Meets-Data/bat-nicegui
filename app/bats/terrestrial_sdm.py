"""Terrestrial SDM create workflow page."""

from dataclasses import dataclass
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

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"climate_periods": ";".join(self.time_periods)}

    def to_parameter_metadata(self) -> dict[str, object]:
        return {"directive_types": self.directive_types}


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

    def selected_time_periods(self) -> list[str]:
        return [
            period
            for period, checkbox in zip(self.time_periods, self.time_period_checks)
            if checkbox.value
        ]


TerrestrialSdmPage.register()
