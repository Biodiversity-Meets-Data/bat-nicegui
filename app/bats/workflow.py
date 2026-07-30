"""Workflow-related shared components and helper functions"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from nicegui import app, ui

from bats.map_widget import MapGeometry, read_map_geometry
from bats.registry import EcosystemCategory
from config import LOCAL_API_BASE_URL


class WorkflowValidationError(Exception):
    """Raised when user-provided workflow inputs fail validation."""


class BatSpecificParameters(ABC):
    """BAT-specific workflow parameters. Self-validating and self-serializing.

    Each BAT must define a subclass that holds its own typed parameters and
    implements validation and serialization.
    """

    __slots__ = ()

    @abstractmethod
    def validate_input(self) -> None:
        """Validate the BAT-specific user inputs and raise a
        WorkflowValidationError if input is invalid.
        """

    @abstractmethod
    def to_api_parameters(self) -> dict[str, Any]:
        """Serialize to the "parameters" dict POSTed to /api/workflows/submit.

        Key order is part of the wire/DB contract and must stay stable.
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowPayload:
    """User-supplied values for a BAT workflow."""

    name: str
    description: str
    species_name: str | None
    ecosystem_type: EcosystemCategory
    geometry: MapGeometry
    bat_specific: BatSpecificParameters

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to the JSON shape expected by /api/workflows/submit."""
        return {
            "name": self.name,
            "description": self.description,
            "species_name": self.species_name or "",
            "ecosystem_type": self.ecosystem_type.slug,  # enum -> "terrestrial"
            "geometry_type": self.geometry.type,
            "geometry_wkt": self.geometry.wkt,
            "parameters": self.bat_specific.to_api_parameters(),
        }


async def build_workflow_payload(
    name: str,
    description: str,
    ecosystem_type: EcosystemCategory,
    bat_specific_parameters: BatSpecificParameters,
    species_name: str | None = None,
    require_species: bool = True,
) -> WorkflowPayload:
    """Validate the common workflow inputs and return a new WorkflowPayload.

    Raises a WorkflowValidationError if a user input is missing or incorrect.
    A BAT without a species input passes ``require_species=False`` to opt out of
    the species requirement; the wire still carries an empty ``species_name``.
    """
    bat_specific_parameters.validate_input()
    if not name:
        raise WorkflowValidationError("Please enter a workflow name")
    if require_species and not species_name:
        raise WorkflowValidationError("Please select a species")

    geometry = await read_map_geometry()
    if geometry is None:
        raise WorkflowValidationError("Please draw an area on the map")

    return WorkflowPayload(
        name=name,
        description=description,
        species_name=species_name,
        ecosystem_type=ecosystem_type,
        geometry=geometry,
        bat_specific=bat_specific_parameters,
    )


async def submit_workflow(payload: WorkflowPayload) -> None:
    """Submit a workflow payload to the app's workflow submission API."""

    auth_token = app.storage.user.get("token")

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{LOCAL_API_BASE_URL}/api/workflows/submit",
                json=payload.to_api_dict(),
                headers={"Authorization": f"Bearer {auth_token}"},
            )
    except httpx.HTTPError as e:
        ui.notify(f"Error: {e}", type="negative")
        return

    if response.status_code == 200:
        result = response.json()
        ui.notify(
            f"Workflow submitted! ID: {result['workflow_id'][:8]}...",
            type="positive",
        )
        ui.run_javascript(
            "if(window.drawnItems) window.drawnItems.clearLayers();",
            timeout=5.0,
        )
        ui.navigate.to("/workflows")
    else:
        ui.notify(f"Error: {response.text}", type="negative")
