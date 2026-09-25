"""Terrestrial CAPTAIN create workflow page."""

from dataclasses import dataclass
from enum import Enum
from nicegui import ui

from bats.base_page import BasePage
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters
from ui_widgets import drop_down_menu, required_int_input


class CaptainAnalysis(Enum):
    SPECIES_RICHNESS = "Species richness"
    ECOSYSTEM_SERVICE = "Ecosystem services value"


class SpeciesSet(Enum):
    DEMO = "Demo species set"
    HABITATS_DIRECTIVE = "Species from the Habitats Directive"
    BIRDS_DIRECTIVE = "Species from the Birds Directive"
    CUSTOM = "Custom species list"


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialCaptainParameters(BatSpecificParameters):
    """BAT-specific workflow parameters for the CAPTAIN BAT."""

    analysis_type: CaptainAnalysis
    species_set: SpeciesSet
    time_steps: int
    generate_report: bool

    def validate_input(self) -> None:
        """CAPTAIN has no additional required inputs to validate."""

    def to_workflow_parameters(self) -> dict[str, str]:
        # Enum member names are used rather than their display labels, so that
        # the values passed to the workflow are stable identifiers.
        return {
            "analysis_type": self.analysis_type.name.lower(),
            "species_set": self.species_set.name.lower(),
            "time_steps": str(self.time_steps),
            "generate_report": str(self.generate_report).lower(),
        }


class TerrestrialCaptainPage(BasePage):
    """CAPTAIN create-workflow page."""

    BAT = get_bat_by_name("terrestrial_captain")

    # ------------------------- Page Construction --------------------------- #

    def add_specific_parameters(self) -> None:
        """Add the BAT-specific parameters (user-input widgets) to the page."""

        # Drop-down menu widgets to select the type of analysis and the species
        # set.
        self.analysis_type = drop_down_menu(
            "Analysis Type", CaptainAnalysis, CaptainAnalysis.SPECIES_RICHNESS
        )
        self.species_set = drop_down_menu(
            "Species Set", SpeciesSet, SpeciesSet.HABITATS_DIRECTIVE
        )

        # Number of time steps of the CAPTAIN analysis.
        self.time_steps = required_int_input(
            "Time steps",
            min=1,
            max=100,
            value=10,
            hint="Number of years in simulation. Max 100 years.",
        )
        # Add PDF report option.
        self.generate_report = ui.checkbox("Generate PDF report", value=True).classes(
            "mt-4"
        )

    def get_specific_parameters(self) -> TerrestrialCaptainParameters:
        return TerrestrialCaptainParameters(
            analysis_type=self.analysis_type.value,
            species_set=self.species_set.value,
            time_steps=self.time_steps.int_value,
            generate_report=bool(self.generate_report.value),
        )


TerrestrialCaptainPage.register()
