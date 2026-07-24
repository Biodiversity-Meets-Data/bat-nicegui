"""Pydantic request models."""

from typing import Any

from pydantic import BaseModel


class WorkflowSubmit(BaseModel):
    name: str
    description: str
    species_name: str
    ecosystem_type: str
    geometry_type: str
    geometry_wkt: str
    parameters: dict[str, Any]


class WorkflowWebhook(BaseModel):
    workflow_id: str
    status: str
    results: dict[str, Any] | None = None
    error_message: str | None = None
