"""Terrestrial CAPTAIN create workflow page."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nicegui import ui

from bats.base_page import BasePage
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters
from ui_widgets import drop_down_menu


class CaptainAnalysis(Enum):
    SPECIES_RICHNESS = "Species richness"
    ECOSYSTEM_SERVICE = "Ecosystem services value"


class SpeciesSet(Enum):
    HABITATS_DIRECTIVE = "Species from the Habitats Directive"
    BIRDS_DIRECTIVE = "Species from the Birds Directive"
    CUSTOM = "Custom species list"


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialCaptainParameters(BatSpecificParameters):
    """BAT-specific workflow parameters for the CAPTAIN BAT."""

    analysis_type: CaptainAnalysis
    species_set: SpeciesSet
    generate_report: bool

    def validate_input(self) -> None:
        """CAPTAIN has no additional required inputs to validate."""

    def to_api_parameters(self) -> dict[str, Any]:
        return {
            "analysis_type": self.analysis_type.value,
            "species_set": self.species_set.value,
            "generate_report": self.generate_report,
        }


class TerrestrialCaptainPage(BasePage):
    """CAPTAIN create-workflow page."""

    BAT = get_bat_by_name("terrestrial_captain")

    # ------------------------- Page Construction --------------------------- #

    def add_specific_parameters(self) -> None:
        """Add the BAT-specific parameters (user-input widgets) to the page."""

        # Add a drop-down menu widgets to select the type of analysis and
        # the species set.
        self.analysis_type = drop_down_menu(
            "Analysis Type", CaptainAnalysis, CaptainAnalysis.SPECIES_RICHNESS
        )
        self.species_set = drop_down_menu(
            "Species Set", SpeciesSet, SpeciesSet.HABITATS_DIRECTIVE
        )

        # Add PDF report option.
        self.generate_report = ui.checkbox("Generate PDF report", value=True).classes(
            "mt-4"
        )

    def get_specific_parameters(self) -> TerrestrialCaptainParameters:
        return TerrestrialCaptainParameters(
            analysis_type=self.analysis_type.value,
            species_set=self.species_set.value,
            generate_report=bool(self.generate_report.value),
        )


TerrestrialCaptainPage.register()
