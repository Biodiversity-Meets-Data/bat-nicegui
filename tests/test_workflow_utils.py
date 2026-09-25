"""Tests for BAT-specific workflow template packaging."""

from io import BytesIO
import zipfile

import pytest

import workflow_utils
from bats.registry import Bat, EcosystemCategory
from workflow_utils import (
    _resolve_template_path,
    build_rocrate_zip,
    declared_workflow_parameters,
    validate_workflow_parameters,
)


def zip_contents(bat_name: str) -> dict[str, str]:
    """Return the packaged template contents for a BAT."""
    archive = build_rocrate_zip(bat_name)
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        return {
            name: zip_file.read(name).decode("utf-8") for name in zip_file.namelist()
        }


@pytest.mark.parametrize(
    ("bat_name", "workflow_marker"),
    [
        ("terrestrial_sdm", "bmd-workflow-"),
        ("terrestrial_captain", "terrestrial-captain-"),
        ("freshwater_sdm", "freshwater-sdm-"),
    ],
)
def test_build_rocrate_zip_uses_bat_templates(
    bat_name: str, workflow_marker: str
) -> None:
    contents = zip_contents(bat_name)

    assert set(contents) == {"workflow.yaml", "ro-crate-metadata.json"}
    assert workflow_marker in contents["workflow.yaml"]


def test_build_rocrate_zip_rejects_unconfigured_bat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unconfigured_bat = Bat(
        name="terrestrial_unconfigured",
        category=EcosystemCategory.TERRESTRIAL,
        label="Unconfigured",
        description="BAT without workflow templates",
        icon="help",
    )
    monkeypatch.setattr(workflow_utils, "get_bat_by_name", lambda _: unconfigured_bat)

    with pytest.raises(ValueError, match="No workflow templates configured"):
        build_rocrate_zip("terrestrial_unconfigured")


def test_build_rocrate_zip_rejects_unknown_bat() -> None:
    with pytest.raises(ValueError, match="Unknown BAT"):
        build_rocrate_zip("not-a-bat")


def test_template_path_cannot_escape_template_root() -> None:
    with pytest.raises(ValueError, match="inside app/templates"):
        _resolve_template_path("../database.py")


def test_yaml_declares_terrestrial_sdm_parameters() -> None:
    declared = declared_workflow_parameters("terrestrial_sdm")

    assert {"target_species", "climate_periods", "aoi_wkt"} <= declared


def test_yaml_declares_freshwater_sdm_parameters() -> None:
    declared = declared_workflow_parameters("freshwater_sdm")

    assert {"target_species", "climate_period", "aoi_wkt"} <= declared


def test_yaml_declares_captain_parameters() -> None:
    declared = declared_workflow_parameters("terrestrial_captain")

    assert {"aoi_wkt", "analysis_type", "species_set", "time_steps"} <= declared


def test_unknown_yaml_parameter_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown workflow parameter"):
        validate_workflow_parameters("terrestrial_sdm", {"not_declared": "value"})
