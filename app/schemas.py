"""Pydantic request models."""

from typing import Any

from pydantic import BaseModel, Field, StrictStr


class WorkflowSubmit(BaseModel):
    name: str
    description: str
    bat_name: str
    species_name: str | None = None
    species_col_id: str | None = None
    ecosystem_type: str
    geometry_type: str
    geometry_wkt: str
    parameters: dict[str, StrictStr]
    parameter_metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowWebhook(BaseModel):
    workflow_id: str
    status: str
    results: dict[str, Any] | None = None
    error_message: str | None = None
