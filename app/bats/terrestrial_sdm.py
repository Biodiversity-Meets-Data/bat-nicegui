"""Terrestrial SDM create workflow page."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
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
    min_observations: float | None
    confidence_threshold: float | None
    include_historical: bool
    generate_report: bool

    def validate_input(self) -> None:
        if not self.directive_types:
            raise WorkflowValidationError("Please choose an EU directive")
        if not self.time_periods:
            raise WorkflowValidationError("Please select a time period")

    def to_api_parameters(self) -> dict[str, Any]:
        return {
            "min_observations": self.min_observations,
            "confidence_threshold": self.confidence_threshold,
            "time_period": ";".join(self.time_periods),
            "directive_types": self.directive_types,
            "include_historical": self.include_historical,
            "generate_report": self.generate_report,
        }


class TerrestrialSdmPage(BasePage):
    """Terrestrial SDM create-workflow page."""

    BAT = get_bat_by_name("terrestrial_sdm")

    def __init__(self) -> None:
        self.ias_species_names = self.load_ias_species_names()
        self.habitat_species_names: list[str] = []
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
            required_label("Choose EU Directive")
            with ui.row().classes("w-full gap-4"):
                self.invasive_cb = (
                    ui.checkbox("Invasive Species", value=False)
                    .props("checked-icon=check_box")
                    .classes("flex-1")
                )
                self.habitat_cb = (
                    ui.checkbox("Habitat", value=False)
                    .props("checked-icon=check_box disable")
                    .classes("flex-1")
                )

        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Species List")
            self.species_select = (
                ui.select(
                    options=self.species_options([]),
                    value=None,
                )
                .props("outlined use-input input-debounce=0 options-html")
                .classes("w-full")
            )

        self.invasive_cb.on_value_change(lambda _: self.update_species_options())
        self.habitat_cb.on_value_change(lambda _: self.update_species_options())
        self.species_select.on_value_change(lambda _: self.update_species_display())

        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Time Period")
            self.time_period_checks = [
                ui.checkbox(period, value=False).classes("w-full")
                for period in self.time_periods
            ]

        ui.label("Additional Parameters").classes(
            "text-sm font-semibold text-gray-600 mt-4 mb-2"
        )

        with ui.row().classes("w-full gap-4 mb-4"):
            self.min_obs = (
                ui.number("Min Observations", value=10)
                .props("outlined")
                .classes("flex-1")
            )
            self.confidence = ui.slider(min=0, max=100, value=80).classes("flex-1")
            ui.label().bind_text_from(
                self.confidence, "value", lambda v: f"Confidence: {v}%"
            )

        self.include_historical = ui.checkbox("Include historical data", value=True)
        self.generate_report = ui.checkbox("Generate PDF report", value=True)

    def get_specific_parameters(self) -> TerrestrialSdmParameters:
        return TerrestrialSdmParameters(
            directive_types=self.selected_directives(),
            time_periods=self.selected_time_periods(),
            min_observations=self.min_obs.value,
            confidence_threshold=self.confidence.value,
            include_historical=bool(self.include_historical.value),
            generate_report=bool(self.generate_report.value),
        )

    def species_name(self) -> str | None:
        species: str | None = self.species_select.value
        return species

    def requires_species(self) -> bool:
        return True

    # --------------------- Species selection helpers ----------------------- #

    @staticmethod
    @lru_cache(maxsize=1)
    def load_ias_species_names() -> tuple[str, ...]:
        """Note: @lru_cache caches the data loaded from the static JSON file.
        To refresh the cache, the application must be re-started.
        """
        static_candidates = [
            Path(__file__).resolve().parent.parent / "static",
            Path(__file__).resolve().parent.parent.parent / "static",
        ]
        static_dir = next(
            (p for p in static_candidates if p.exists()), static_candidates[0]
        )
        ias_path = static_dir / "eu-ias-directive.json"
        try:
            with ias_path.open("r", encoding="utf-8") as handle:
                ias_data = json.load(handle)
        except Exception:
            ias_data = []
        return tuple(
            entry.get("scientificName", "").strip()
            for entry in ias_data
            if entry.get("scientificName")
        )

    def species_options(self, selected_directives: list[str]) -> dict[str, str]:
        options: dict[str, str] = {}
        if "invasive_species" in selected_directives:
            for name in self.ias_species_names:
                options[name] = f"{name} <span class='species-pill'>IAS</span>"
        if "habitat" in selected_directives:
            for name in self.habitat_species_names:
                options[name] = f"{name} <span class='species-pill'>HAB</span>"
        return options

    def selected_directives(self) -> list[str]:
        directive_types: list[str] = []
        if self.invasive_cb.value:
            directive_types.append("invasive_species")
        if self.habitat_cb.value:
            directive_types.append("habitat")
        return directive_types

    def selected_time_periods(self) -> list[str]:
        return [
            period
            for period, checkbox in zip(self.time_periods, self.time_period_checks)
            if checkbox.value
        ]

    def update_species_options(self) -> None:
        selected = self.selected_directives()
        self.species_select.options = self.species_options(selected)
        if self.species_select.value not in self.species_select.options:
            self.species_select.value = None
        self.species_select.update()

    def update_species_display(self) -> None:
        self.species_select.props(
            f"display-value={json.dumps(self.species_select.value or '')}"
        )
        self.species_select.update()


TerrestrialSdmPage.register()
