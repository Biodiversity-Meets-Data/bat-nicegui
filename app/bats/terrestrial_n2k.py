"""Natura 2000 occurrence and habitat mapping workflow page."""

from dataclasses import dataclass
from datetime import date

from nicegui import ui

from bats.base_page import BasePage
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters, WorkflowValidationError
from ui_widgets import required_int_input, required_label


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialN2kParameters(BatSpecificParameters):
    """Natura 2000 temporal and spatial workflow parameters."""

    min_year: int
    max_year: int

    def validate_input(self) -> None:
        if self.min_year > self.max_year:
            raise WorkflowValidationError("Start year must be before end year")

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"min_year": str(self.min_year), "max_year": str(self.max_year)}

    def to_parameter_metadata(self) -> dict[str, object]:
        return {"min_year": self.min_year, "max_year": self.max_year}


class TerrestrialN2kPage(BasePage):
    """Natura 2000 create-workflow page."""

    BAT = get_bat_by_name("terrestrial_n2k")

    def __init__(self) -> None:
        self.current_year = date.today().year
        super().__init__()

    def add_specific_parameters(self) -> None:
        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Observation Period")
            with ui.row().classes("w-full gap-3"):
                self.min_year_input = required_int_input(
                    "Start Year", min=1600, max=self.current_year, value=2020
                ).classes("flex-1")
                self.max_year_input = required_int_input(
                    "End Year",
                    min=1600,
                    max=self.current_year,
                    value=self.current_year,
                ).classes("flex-1")

    def get_specific_parameters(self) -> TerrestrialN2kParameters:
        return TerrestrialN2kParameters(
            min_year=self.min_year_input.int_value,
            max_year=self.max_year_input.int_value,
        )


TerrestrialN2kPage.register()
