"""Fetch and present Natura2000 site metadata from the BMD Dataspace."""

from collections.abc import Mapping
import json
from typing import Any
from urllib.parse import quote

import httpx

SITE_METADATA_URL = "https://dataspace.bmdproject.eu/sites/{site_code}/metadata/BISE"

SITE_METADATA_FIELDS: tuple[tuple[str, str], ...] = (
    ("siteName", "Site name"),
    ("siteCode", "Site code"),
    ("designation", "Designation"),
    ("siteType", "Site type"),
    ("countryName", "Country"),
    ("countryCode", "Country code"),
    ("regions", "Regions"),
    ("majorEcosystemType", "Major ecosystem type"),
    ("areaHa", "Area (ha)"),
    ("areaKm2", "Area (km²)"),
    ("numberProtectedHabitatTypes", "Protected habitat types"),
    ("numberProtectedSpecies", "Protected species"),
    ("managementPlan", "Management plan"),
    ("siteDescription", "Site description"),
    ("yearEstablished", "Year established"),
)


class NaturaMetadataError(RuntimeError):
    """Raised when site metadata cannot be fetched or decoded."""


async def fetch_natura_site_metadata(site_code: str) -> dict[str, Any]:
    """Fetch a site's BISE metadata JSON from the BMD Dataspace."""
    normalized_site_code = site_code.strip()
    if not normalized_site_code:
        raise NaturaMetadataError("A Natura2000 site code is required")

    url = SITE_METADATA_URL.format(site_code=quote(normalized_site_code, safe=""))
    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.get(url)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise NaturaMetadataError(
            "The Natura2000 metadata service could not be reached"
        ) from exc
    except ValueError as exc:
        raise NaturaMetadataError(
            "The Natura2000 metadata response was not valid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise NaturaMetadataError("The Natura2000 metadata response was not an object")
    return payload


def format_natura_metadata_value(value: Any) -> str:
    """Convert one metadata value to readable text, preserving API strings."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return "Not provided"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def natura_metadata_rows(metadata: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    """Return known metadata fields in the user-facing display order."""
    return tuple(
        (label, format_natura_metadata_value(metadata.get(key)))
        for key, label in SITE_METADATA_FIELDS
    )
