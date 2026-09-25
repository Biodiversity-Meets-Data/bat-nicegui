"""Tests for the form fields sent to the workflow API on submission.

The tests use BAT parameter classes defined here rather than those of real
BATs, so that they don't need updating when a BAT's parameters change.
"""

from dataclasses import dataclass
import pytest

import workflow_utils
from bats.map_widget import MapGeometry
from bats.registry import EcosystemCategory
from bats.workflow import BatSpecificParameters, WorkflowPayload
from schemas import WorkflowSubmit
from workflow_utils import build_workflow_api_form_data

AOI_WKT = "POLYGON ((8 49, 12 49, 12 50, 8 50, 8 49))"
WEBHOOK_URL = "http://bmd-bat-app:8080/api/workflows/webhook/{workflow_id}"

# Fields sent for every BAT, with the settings of the fixture below.
COMMON_FIELDS = {
    "webhook_url": WEBHOOK_URL,
    "dry_run": "false",
    "force": "false",
    "param-aoi_wkt": AOI_WKT,
}


@pytest.fixture(autouse=True)
def workflow_api_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use fixed workflow API settings, independent of the environment."""
    monkeypatch.setattr(workflow_utils, "WORKFLOW_WEBHOOK_URL_TEMPLATE", WEBHOOK_URL)
    monkeypatch.setattr(workflow_utils, "WORKFLOW_DRY_RUN", False)
    monkeypatch.setattr(workflow_utils, "WORKFLOW_FORCE", False)


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnWorkflowParameters(BatSpecificParameters):
    """Parameters of a BAT that supplies its own workflow parameters."""

    parameters: dict[str, str]

    def validate_input(self) -> None:
        pass

    def to_workflow_parameters(self) -> dict[str, str]:
        return self.parameters


def submitted(
    bat_specific: BatSpecificParameters,
    species_col_id: str | None = None,
) -> WorkflowSubmit:
    """Return the request body received by the submit endpoint, built the same
    way as by a BAT page.
    """
    payload = WorkflowPayload(
        name="test",
        description="",
        bat_name="test_bat",
        species_name="Myotis myotis" if species_col_id else None,
        species_col_id=species_col_id,
        ecosystem_type=EcosystemCategory.TERRESTRIAL,
        geometry=MapGeometry(type="polygon", wkt=AOI_WKT),
        bat_specific=bat_specific,
    )
    return WorkflowSubmit(**payload.to_api_dict())


def test_yaml_parameters_are_sent_with_param_prefix() -> None:
    workflow = submitted(
        OwnWorkflowParameters(
            parameters={"time_steps": "10", "analysis_type": "richness"}
        )
    )

    assert build_workflow_api_form_data(workflow) == COMMON_FIELDS | {
        "param-time_steps": "10",
        "param-analysis_type": "richness",
    }


def test_empty_workflow_parameters_add_no_bat_specific_fields() -> None:
    workflow = submitted(OwnWorkflowParameters(parameters={}))

    assert build_workflow_api_form_data(workflow) == COMMON_FIELDS


def test_selected_species_is_sent_as_target_species() -> None:
    workflow = submitted(OwnWorkflowParameters(parameters={}), species_col_id="456G3")

    assert build_workflow_api_form_data(workflow) == COMMON_FIELDS | {
        "param-target_species": "456G3",
    }


def test_no_webhook_url_when_template_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow_utils, "WORKFLOW_WEBHOOK_URL_TEMPLATE", "")
    workflow = submitted(OwnWorkflowParameters(parameters={}))

    assert "webhook_url" not in build_workflow_api_form_data(workflow)
