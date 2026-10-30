"""Camera-trap occupancy trend workflow page."""

from dataclasses import dataclass

from nicegui import ui

from bats.base_page import BasePage
from bats.camtrap_data import CameraDataset, load_ctocc_datasets
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters, WorkflowValidationError
from ui_widgets import required_label


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialCtoccParameters(BatSpecificParameters):
    """Parameters for the CT-OCC workflow."""

    dataset: CameraDataset
    target_species: str

    def validate_input(self) -> None:
        if not self.dataset.url:
            raise WorkflowValidationError("Please select a camera-trap dataset")
        if not self.target_species:
            raise WorkflowValidationError("Please select a target species")

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"url": self.dataset.url, "target_species": self.target_species}

    def to_parameter_metadata(self) -> dict[str, object]:
        return {
            "dataset": self.dataset.name,
            "dataset_key": self.dataset.key,
            "target_species": self.target_species,
        }


class TerrestrialCtoccPage(BasePage):
    """Camera-trap occupancy trend create-workflow page."""

    BAT = get_bat_by_name("terrestrial_ctocc")

    def __init__(self) -> None:
        self.datasets = load_ctocc_datasets()
        self.datasets_by_key = {dataset.key: dataset for dataset in self.datasets}
        super().__init__()

    def add_specific_parameters(self) -> None:
        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Camera-trap Dataset")
            self.dataset_select = (
                ui.select(
                    options={dataset.key: dataset.name for dataset in self.datasets},
                    value=None,
                )
                .props("outlined use-input input-debounce=200 clearable")
                .classes("w-full")
            )

            self.dataset_select.on_value_change(self._update_species_options)

        with ui.column().classes("w-full gap-1 mt-4"):
            required_label("Target Species")
            self.ctocc_species_select = (
                ui.select(options={}, value=None)
                .props("outlined use-input input-debounce=0 clearable")
                .classes("w-full")
            )

    def _update_species_options(self, event: object) -> None:
        dataset_key = getattr(event, "value", None)
        dataset = self.datasets_by_key.get(str(dataset_key))
        self.ctocc_species_select.options = {
            species: species for species in (dataset.species if dataset else ())
        }
        self.ctocc_species_select.value = None
        self.ctocc_species_select.update()

    def get_specific_parameters(self) -> TerrestrialCtoccParameters:
        dataset = self.datasets_by_key.get(str(self.dataset_select.value))
        if dataset is None:
            raise WorkflowValidationError("Please select a camera-trap dataset")
        return TerrestrialCtoccParameters(
            dataset=dataset,
            target_species=str(self.ctocc_species_select.value or "").strip(),
        )


TerrestrialCtoccPage.register()
