"""Tests for the BAT registry."""

import pytest

from bats.map_widget import MapSelectionMode
from bats.registry import BAT_REGISTRY, Bat, EcosystemCategory
from species import SpeciesList


@pytest.mark.parametrize("bat", BAT_REGISTRY, ids=lambda bat: bat.name)
def test_every_bat_has_about_markdown_file(bat: Bat) -> None:
    """Every registered BAT must ship a readable, non-empty about markdown file.

    Reads through the same property the UI uses, so a missing or misnamed file
    fails here in CI instead of raising when a user opens the "About" dialog.
    """

    # If the about file does not exist, an exception is raised.
    assert bat.about_md.strip(), f"about markdown for {bat.name!r} is empty"


def test_about_md_raises_when_file_missing() -> None:
    """Accessing the 'about' must raise an error when the file is missing."""

    bat = Bat(
        name="non_existent_test_bat",
        category=EcosystemCategory.TERRESTRIAL,
        label="A test BAT",
        description="A test BAT with no about markdown file.",
        icon="star",
    )
    with pytest.raises(FileNotFoundError):
        _ = bat.about_md


def test_spatial_bats_enable_all_map_selection_modes() -> None:
    """Existing spatial BATs expose drawing, country, and Natura2000 selection."""
    spatial_bats = [
        bat
        for bat in BAT_REGISTRY
        if bat.name
        not in {
            "terrestrial_camtrap",
            "terrestrial_ctocc",
            "terrestrial_n2k",
        }
    ]
    assert all(
        bat.map_selection_modes == frozenset(MapSelectionMode) for bat in spatial_bats
    )


def test_camera_bats_do_not_require_a_map() -> None:
    assert all(
        next(bat for bat in BAT_REGISTRY if bat.name == name).map_selection_modes
        == frozenset()
        for name in ("terrestrial_camtrap", "terrestrial_ctocc")
    )


def test_n2k_uses_only_natura2000_selection() -> None:
    n2k = next(bat for bat in BAT_REGISTRY if bat.name == "terrestrial_n2k")
    assert n2k.map_selection_modes == frozenset({MapSelectionMode.NATURA2000})


def test_freshwater_sdm_excludes_birds_directive_species_lists() -> None:
    freshwater_sdm = next(bat for bat in BAT_REGISTRY if bat.name == "freshwater_sdm")

    assert freshwater_sdm.species_lists == (
        SpeciesList.HABITATS_ANNEX_II,
        SpeciesList.HABITATS_ANNEX_IV,
        SpeciesList.HABITATS_ANNEX_V,
        SpeciesList.HABITATS_CHARACTERISTIC_ANNEX_I,
        SpeciesList.IAS_UNION_CONCERN,
    )


def test_ctocc_uses_dataset_specific_species_lists() -> None:
    ctocc = next(bat for bat in BAT_REGISTRY if bat.name == "terrestrial_ctocc")

    assert ctocc.species_lists == ()
