"""Tests for the shared species catalog."""

from species import (
    ALL_SELECTABLE_SPECIES_LISTS,
    SPECIES_LIST_DEFINITIONS,
    load_species_options,
)


def test_updated_species_lists_load_without_legacy_asset() -> None:
    options = load_species_options(ALL_SELECTABLE_SPECIES_LISTS)

    assert options
    assert all(option.col_id for option in options)
    assert all(option.scientific_name for option in options)
    assert "eu-ias-directive.json" not in {
        definition.filename for definition in SPECIES_LIST_DEFINITIONS.values()
    }


def test_duplicate_col_ids_are_merged_with_multiple_list_memberships() -> None:
    options = load_species_options(ALL_SELECTABLE_SPECIES_LISTS)
    duplicated = [option for option in options if len(option.list_labels) > 1]

    assert duplicated
    assert all(option.scientific_name in option.html_label for option in duplicated)
