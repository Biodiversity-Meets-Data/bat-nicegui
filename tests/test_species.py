"""Tests for the shared species catalog."""

from species import (
    ALL_SELECTABLE_SPECIES_LISTS,
    SpeciesList,
    SPECIES_LIST_DEFINITIONS,
    available_species_directives,
    load_species_options,
)


def test_updated_species_lists_load_without_legacy_asset() -> None:
    options = load_species_options(ALL_SELECTABLE_SPECIES_LISTS, "terrestrial")

    assert options
    assert all(option.col_id for option in options)
    assert all(option.scientific_name for option in options)
    assert "eu-ias-directive.json" not in {
        definition.filename for definition in SPECIES_LIST_DEFINITIONS.values()
    }


def test_duplicate_col_ids_are_merged_with_multiple_list_memberships() -> None:
    options = load_species_options(ALL_SELECTABLE_SPECIES_LISTS, "terrestrial")
    duplicated = [option for option in options if len(option.list_labels) > 1]

    assert duplicated
    assert all(option.scientific_name in option.html_label for option in duplicated)


def test_available_directives_follow_configured_species_lists() -> None:
    freshwater_lists = (
        SpeciesList.IAS_UNION_CONCERN,
        SpeciesList.HABITATS_ANNEX_II,
    )

    assert available_species_directives(freshwater_lists) == (
        "invasive_species",
        "habitat",
    )
    assert available_species_directives(()) == ()


def test_species_options_filter_records_by_realm(monkeypatch) -> None:
    import species

    records_by_file = {
        "Habitats_Directive_Annex_II.json": [
            {
                "colId": "shared",
                "scientificName": "Shared species",
                "realm": "terrestrial",
            },
            {
                "colId": "shared",
                "scientificName": "Shared species",
                "realm": "freshwater",
            },
            {"colId": "marine", "scientificName": "Marine species", "realm": "marine"},
            {"colId": "missing", "scientificName": "Missing realm"},
            {"colId": "unknown", "scientificName": "Unknown realm", "realm": "soil"},
        ],
        "Habitats_Directive_Annex_IV.json": [
            {
                "colId": "shared",
                "scientificName": "Shared species",
                "realm": "freshwater",
            },
            {
                "colId": "freshwater",
                "scientificName": "Freshwater species",
                "realm": "FRESHWATER",
            },
        ],
    }
    monkeypatch.setattr(
        species,
        "_read_records",
        lambda path: records_by_file.get(path.name, []),
    )
    load_species_options.cache_clear()

    list_ids = (SpeciesList.HABITATS_ANNEX_II, SpeciesList.HABITATS_ANNEX_IV)
    terrestrial = load_species_options(list_ids, "terrestrial")
    freshwater = load_species_options(list_ids, "Freshwater")
    marine = load_species_options(list_ids, "marine")

    assert [(option.col_id, option.list_labels) for option in terrestrial] == [
        ("shared", ("Habitats Directive Annex II",))
    ]
    assert [(option.col_id, option.list_labels) for option in freshwater] == [
        ("freshwater", ("Habitats Directive Annex IV",)),
        (
            "shared",
            ("Habitats Directive Annex II", "Habitats Directive Annex IV"),
        ),
    ]
    assert [option.col_id for option in marine] == ["marine"]
    assert load_species_options(list_ids, "unknown-realm") == ()

    load_species_options.cache_clear()


def test_species_loader_cache_includes_realm() -> None:
    load_species_options.cache_clear()

    terrestrial = load_species_options((SpeciesList.HABITATS_ANNEX_II,), "terrestrial")
    freshwater = load_species_options((SpeciesList.HABITATS_ANNEX_II,), "freshwater")

    assert terrestrial
    assert freshwater
    assert {option.col_id for option in terrestrial} != {
        option.col_id for option in freshwater
    }

    load_species_options.cache_clear()
