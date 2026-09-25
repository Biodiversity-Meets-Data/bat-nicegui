"""Helpers for workflow API integration and RO-Crate packaging."""

from functools import lru_cache
import tempfile
import zipfile
from pathlib import Path

import yaml

from bats.registry import get_bat_by_name
from config import (
    TEMPLATES_DIR,
    WORKFLOW_API_AUTH_HEADER,
    WORKFLOW_API_AUTH_SCHEME,
    WORKFLOW_API_KEY,
    WORKFLOW_DRY_RUN,
    WORKFLOW_FORCE,
    WORKFLOW_WEBHOOK_URL_TEMPLATE,
)
from schemas import WorkflowSubmit


def build_rocrate_zip(bat_name: str) -> bytes:
    """Package the configured static templates for one BAT."""
    try:
        bat = get_bat_by_name(bat_name)
    except KeyError as exc:
        raise ValueError(f"Unknown BAT: {bat_name}") from exc

    if not bat.workflow_yaml_path or not bat.rocrate_path:
        raise ValueError(f"No workflow templates configured for BAT: {bat_name}")

    workflow_path = _resolve_template_path(bat.workflow_yaml_path)
    rocrate_path = _resolve_template_path(bat.rocrate_path)
    workflow_rendered = workflow_path.read_text(encoding="utf-8")
    rocrate_rendered = rocrate_path.read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workflow_file = temp_path / "workflow.yaml"
        rocrate_file = temp_path / "ro-crate-metadata.json"
        workflow_file.write_text(workflow_rendered, encoding="utf-8")
        rocrate_file.write_text(rocrate_rendered, encoding="utf-8")

        zip_path = temp_path / "rocrate.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(workflow_file, arcname="workflow.yaml")
            zip_file.write(rocrate_file, arcname="ro-crate-metadata.json")

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            contents = [
                f"{info.filename} ({info.file_size} bytes)"
                for info in zip_file.infolist()
            ]
            print(f"RO-Crate contents: {contents}")

        return zip_path.read_bytes()


def _resolve_template_path(relative_path: str) -> Path:
    """Resolve a registered template path without leaving the template root."""
    template_root = TEMPLATES_DIR.resolve()
    candidate = (template_root / relative_path).resolve()
    try:
        candidate.relative_to(template_root)
    except ValueError as exc:
        raise ValueError("Workflow template path must be inside app/templates") from exc
    if not candidate.is_file():
        raise ValueError(f"Workflow template does not exist: {relative_path}")
    return candidate


def build_workflow_api_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if WORKFLOW_API_KEY:
        if WORKFLOW_API_AUTH_SCHEME:
            headers[WORKFLOW_API_AUTH_HEADER] = (
                f"{WORKFLOW_API_AUTH_SCHEME} {WORKFLOW_API_KEY}"
            )
        else:
            headers[WORKFLOW_API_AUTH_HEADER] = WORKFLOW_API_KEY
    return headers


def build_workflow_api_form_data(workflow: WorkflowSubmit) -> dict[str, str]:
    """Build the 'form fields' data sent to the workflow API with the RO-Crate
    ZIP.

    Fields prefixed with 'param-' set the Argo workflow parameter of the same
    name (without the prefix) in the BAT's workflow template.
    """
    data: dict[str, str] = {
        "dry_run": str(WORKFLOW_DRY_RUN).lower(),
        "force": str(WORKFLOW_FORCE).lower(),
    }
    for name, value in workflow.parameters.items():
        data[f"param-{name}"] = value

    if WORKFLOW_WEBHOOK_URL_TEMPLATE:
        data["webhook_url"] = WORKFLOW_WEBHOOK_URL_TEMPLATE
    return data


@lru_cache(maxsize=None)
def declared_workflow_parameters(bat_name: str) -> frozenset[str]:
    """Read the top-level Argo parameter names declared by a BAT template."""
    try:
        bat = get_bat_by_name(bat_name)
    except KeyError as exc:
        raise ValueError(f"Unknown BAT: {bat_name}") from exc
    if not bat.workflow_yaml_path:
        raise ValueError(f"No workflow template configured for BAT: {bat_name}")

    workflow_path = _resolve_template_path(bat.workflow_yaml_path)
    try:
        document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid workflow YAML for BAT: {bat_name}") from exc

    parameter_definitions = (
        document.get("spec", {}).get("arguments", {}).get("parameters", [])
        if isinstance(document, dict)
        else []
    )
    if not isinstance(parameter_definitions, list):
        raise ValueError(f"Workflow YAML has invalid parameters for BAT: {bat_name}")

    names = {
        item["name"]
        for item in parameter_definitions
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if not names:
        raise ValueError(f"Workflow YAML declares no parameters for BAT: {bat_name}")
    return frozenset(names)


def validate_workflow_parameters(bat_name: str, parameters: dict[str, str]) -> None:
    """Reject submitted parameters that are absent from the BAT YAML."""
    declared = declared_workflow_parameters(bat_name)
    unknown = sorted(set(parameters) - declared)
    if unknown:
        names = ", ".join(unknown)
        raise ValueError(f"Unknown workflow parameter(s) for {bat_name}: {names}")
