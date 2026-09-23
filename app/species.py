"""Shared species-list definitions and loading helpers."""

from dataclasses import dataclass
from enum import StrEnum
import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from collections.abc import Iterable


class SpeciesList(StrEnum):
    """Stable identifiers for the supported server-side species lists."""

    BIRDS_ANNEX_I = "birds_annex_i"
    BIRDS_ANNEX_II = "birds_annex_ii"
    BIRDS_ANNEX_III = "birds_annex_iii"
    HABITATS_ANNEX_II = "habitats_annex_ii"
    HABITATS_ANNEX_IV = "habitats_annex_iv"
    HABITATS_ANNEX_V = "habitats_annex_v"
    HABITATS_CHARACTERISTIC_ANNEX_I = "habitats_characteristic_annex_i"
    IAS_UNION_CONCERN = "ias_union_concern"


@dataclass(frozen=True, slots=True)
class SpeciesListDefinition:
    """Human-facing metadata for one species list asset."""

    label: str
    filename: str


SPECIES_LIST_DEFINITIONS: dict[SpeciesList, SpeciesListDefinition] = {
    SpeciesList.BIRDS_ANNEX_I: SpeciesListDefinition(
        "Birds Directive Annex I", "Birds_Directive_Annex_I.json"
    ),
    SpeciesList.BIRDS_ANNEX_II: SpeciesListDefinition(
        "Birds Directive Annex II", "Birds_Directive_Annex_II.json"
    ),
    SpeciesList.BIRDS_ANNEX_III: SpeciesListDefinition(
        "Birds Directive Annex III", "Birds_Directive_Annex_III.json"
    ),
    SpeciesList.HABITATS_ANNEX_II: SpeciesListDefinition(
        "Habitats Directive Annex II", "Habitats_Directive_Annex_II.json"
    ),
    SpeciesList.HABITATS_ANNEX_IV: SpeciesListDefinition(
        "Habitats Directive Annex IV", "Habitats_Directive_Annex_IV.json"
    ),
    SpeciesList.HABITATS_ANNEX_V: SpeciesListDefinition(
        "Habitats Directive Annex V", "Habitats_Directive_Annex_V.json"
    ),
    SpeciesList.HABITATS_CHARACTERISTIC_ANNEX_I: SpeciesListDefinition(
        "Habitats Characteristic Species Annex I",
        "Habitats_Directive_Characteristic_Species_Annex_I.json",
    ),
    SpeciesList.IAS_UNION_CONCERN: SpeciesListDefinition(
        "Invasive Alien Species of Union Concern",
        "Invasive_Alien_Species_of_Union_Concern.json",
    ),
}

ALL_SELECTABLE_SPECIES_LISTS: tuple[SpeciesList, ...] = tuple(SpeciesList)

DIRECTIVE_SPECIES_LISTS: dict[str, tuple[SpeciesList, ...]] = {
    "invasive_species": (SpeciesList.IAS_UNION_CONCERN,),
    "bird": (
        SpeciesList.BIRDS_ANNEX_I,
        SpeciesList.BIRDS_ANNEX_II,
        SpeciesList.BIRDS_ANNEX_III,
    ),
    "habitat": (
        SpeciesList.HABITATS_ANNEX_II,
        SpeciesList.HABITATS_ANNEX_IV,
        SpeciesList.HABITATS_ANNEX_V,
        SpeciesList.HABITATS_CHARACTERISTIC_ANNEX_I,
    ),
}

SPECIES_PILL_STYLES: dict[str, str] = {
    "species-pill--ias-union-concern": "background:rgba(220,38,38,.14);color:#b91c1c",
    "species-pill--habitats-annex-ii": "background:rgba(37,99,235,.16);color:#1d4ed8",
    "species-pill--habitats-annex-iv": "background:rgba(37,99,235,.28);color:#1e40af",
    "species-pill--habitats-annex-v": "background:rgba(37,99,235,.42);color:#1e3a8a",
    "species-pill--habitats-characteristic-annex-i": "background:rgba(37,99,235,.10);color:#2563eb",
    "species-pill--birds-annex-i": "background:rgba(147,51,234,.16);color:#7e22ce",
    "species-pill--birds-annex-ii": "background:rgba(147,51,234,.28);color:#6b21a8",
    "species-pill--birds-annex-iii": "background:rgba(147,51,234,.42);color:#581c87",
}


@dataclass(frozen=True, slots=True)
class SpeciesOption:
    """A merged selector option with all lists containing the species."""

    col_id: str
    scientific_name: str
    list_labels: tuple[str, ...]
    list_pill_classes: tuple[str, ...]

    @property
    def html_label(self) -> str:
        """Return the option label used by the searchable HTML select."""
        pills = " ".join(
            f"<span class='species-pill {pill_class}' "
            f"style='{SPECIES_PILL_STYLES[pill_class]}'>{label}</span>"
            for label, pill_class in zip(self.list_labels, self.list_pill_classes)
        )
        return (
            f"{self.scientific_name} {pills} "
            f"<span class='text-gray-400 text-xs'>{self.col_id}</span>"
        )


def _static_directory() -> Path:
    """Locate static assets in both local and container layouts."""
    candidates = (
        Path(__file__).resolve().parent.parent / "static",
        Path(__file__).resolve().parent / "static",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def _read_records(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    return [record for record in data if isinstance(record, dict)]


@lru_cache(maxsize=None)
def load_species_options(
    list_ids: tuple[SpeciesList, ...],
) -> tuple[SpeciesOption, ...]:
    """Load and merge species records from the configured static lists."""
    merged: dict[str, tuple[str, list[str], list[str]]] = {}
    static_directory = _static_directory()

    for list_id in list_ids:
        definition = SPECIES_LIST_DEFINITIONS[list_id]
        for record in _read_records(static_directory / definition.filename):
            col_id = str(record.get("colId", "")).strip()
            scientific_name = str(record.get("scientificName", "")).strip()
            if not col_id or not scientific_name:
                continue
            pill_class = f"species-pill--{list_id.value.replace('_', '-')}"
            if col_id not in merged:
                merged[col_id] = (scientific_name, [definition.label], [pill_class])
            elif definition.label not in merged[col_id][1]:
                merged[col_id][1].append(definition.label)
                merged[col_id][2].append(pill_class)

    return tuple(
        SpeciesOption(
            col_id=col_id,
            scientific_name=scientific_name,
            list_labels=tuple(list_labels),
            list_pill_classes=tuple(list_pill_classes),
        )
        for col_id, (scientific_name, list_labels, list_pill_classes) in sorted(
            merged.items(), key=lambda item: (item[1][0].casefold(), item[0])
        )
        if list_pill_classes
    )


def species_lists_for_directives(
    directives: Iterable[str], allowed_lists: tuple[SpeciesList, ...]
) -> tuple[SpeciesList, ...]:
    """Return configured species assets belonging to selected directives."""
    selected_lists = {
        list_id
        for directive in directives
        for list_id in DIRECTIVE_SPECIES_LISTS.get(directive, ())
    }
    return tuple(list_id for list_id in allowed_lists if list_id in selected_lists)
