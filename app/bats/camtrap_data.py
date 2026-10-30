"""Static Camtrap DP datasets used by the camera-trap BAT pages."""

from dataclasses import dataclass
import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _static_directory() -> Path:
    """Locate static assets in local and container layouts."""
    candidates = (
        Path(__file__).resolve().parent.parent / "static",
        Path(__file__).resolve().parent.parent.parent / "static",
    )
    for directory in candidates:
        if directory.is_dir():
            return directory
    return candidates[0]


@dataclass(frozen=True, slots=True)
class CameraDataset:
    """A published Camtrap DP dataset selectable by a user."""

    name: str
    key: str
    url: str
    species: tuple[str, ...] = ()


def _load_datasets(filename: str) -> tuple[CameraDataset, ...]:
    path = _static_directory() / filename
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not load camera dataset catalog: {filename}") from exc

    if not isinstance(raw, list):
        raise ValueError(f"Camera dataset catalog must be a list: {filename}")

    datasets: list[CameraDataset] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Invalid dataset entry {index} in {filename}")
        name = item.get("dataset")
        key = item.get("datasetKey")
        url = item.get("url")
        species = item.get("species", [])
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Dataset entry {index} is missing required fields")
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"Dataset entry {index} is missing required fields")
        if not isinstance(url, str) or not url.strip():
            raise ValueError(f"Dataset entry {index} is missing required fields")
        if not isinstance(species, list) or not all(
            isinstance(value, str) and value.strip() for value in species
        ):
            raise ValueError(f"Dataset entry {index} has invalid species")
        datasets.append(
            CameraDataset(
                name=name.strip(),
                key=key.strip(),
                url=url.strip(),
                species=tuple(species),
            )
        )
    return tuple(datasets)


@lru_cache(maxsize=1)
def load_camtrap_datasets() -> tuple[CameraDataset, ...]:
    """Load the datasets available to the camera-summary BAT."""
    return _load_datasets("bat-camtrap.json")


@lru_cache(maxsize=1)
def load_ctocc_datasets() -> tuple[CameraDataset, ...]:
    """Load the datasets and species available to the CT-OCC BAT."""
    return _load_datasets("bat-ctocc.json")
