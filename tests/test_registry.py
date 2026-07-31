"""Tests for the BAT registry."""

import pytest

from bats.registry import BAT_REGISTRY, Bat, EcosystemCategory


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
