"""Tests for BAT-specific workflow template packaging."""

from io import BytesIO
import zipfile

import pytest

from workflow_utils import _resolve_template_path, build_rocrate_zip


def zip_contents(bat_name: str) -> dict[str, str]:
    """Return the packaged template contents for a BAT."""
    archive = build_rocrate_zip(bat_name, {})
    with zipfile.ZipFile(BytesIO(archive)) as zip_file:
        return {
            name: zip_file.read(name).decode("utf-8") for name in zip_file.namelist()
        }


@pytest.mark.parametrize(
    ("bat_name", "workflow_marker"),
    [
        ("terrestrial_sdm", "bmd-workflow-"),
        ("freshwater_sdm", "freshwater-sdm-"),
    ],
)
def test_build_rocrate_zip_uses_bat_templates(
    bat_name: str, workflow_marker: str
) -> None:
    contents = zip_contents(bat_name)

    assert set(contents) == {"workflow.yaml", "ro-crate-metadata.json"}
    assert workflow_marker in contents["workflow.yaml"]


def test_build_rocrate_zip_rejects_unconfigured_bat() -> None:
    with pytest.raises(ValueError, match="No workflow templates configured"):
        build_rocrate_zip("terrestrial_captain", {})


def test_build_rocrate_zip_rejects_unknown_bat() -> None:
    with pytest.raises(ValueError, match="Unknown BAT"):
        build_rocrate_zip("not-a-bat", {})


def test_template_path_cannot_escape_template_root() -> None:
    with pytest.raises(ValueError, match="inside app/templates"):
        _resolve_template_path("../database.py")
