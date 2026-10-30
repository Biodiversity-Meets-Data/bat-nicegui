"""Tests for the static camera-trap dataset catalogs."""

from bats.camtrap_data import load_camtrap_datasets, load_ctocc_datasets


def test_camtrap_catalog_contains_valid_datasets() -> None:
    datasets = load_camtrap_datasets()

    assert datasets
    assert all(dataset.name and dataset.key and dataset.url for dataset in datasets)
    assert all(not dataset.species for dataset in datasets)


def test_ctocc_catalog_contains_dataset_specific_species() -> None:
    datasets = load_ctocc_datasets()

    assert datasets
    assert all(dataset.species for dataset in datasets)
    assert any("Sus scrofa" in dataset.species for dataset in datasets)
