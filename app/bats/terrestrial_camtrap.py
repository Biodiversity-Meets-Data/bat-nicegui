"""Camera-trap species and activity summary workflow page."""

from dataclasses import dataclass

from nicegui import ui

from bats.base_page import BasePage
from bats.camtrap_data import CameraDataset, load_camtrap_datasets
from bats.registry import get_bat_by_name
from bats.workflow import BatSpecificParameters, WorkflowValidationError
from ui_widgets import required_label


@dataclass(frozen=True, slots=True, kw_only=True)
class TerrestrialCamtrapParameters(BatSpecificParameters):
    """Parameters for the Camtrap DP summary workflow."""

    dataset: CameraDataset

    def validate_input(self) -> None:
        if not self.dataset.url:
            raise WorkflowValidationError("Please select a camera-trap dataset")

    def to_workflow_parameters(self) -> dict[str, str]:
        return {"url": self.dataset.url}

    def to_parameter_metadata(self) -> dict[str, object]:
        return {"dataset": self.dataset.name, "dataset_key": self.dataset.key}


class TerrestrialCamtrapPage(BasePage):
    """Camera-trap summary create-workflow page."""

    BAT = get_bat_by_name("terrestrial_camtrap")

    def __init__(self) -> None:
        self.datasets = load_camtrap_datasets()
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

    def get_specific_parameters(self) -> TerrestrialCamtrapParameters:
        selected = next(
            (
                dataset
                for dataset in self.datasets
                if dataset.key == self.dataset_select.value
            ),
            None,
        )
        if selected is None:
            raise WorkflowValidationError("Please select a camera-trap dataset")
        return TerrestrialCamtrapParameters(dataset=selected)


TerrestrialCamtrapPage.register()
