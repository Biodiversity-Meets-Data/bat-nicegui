"""Helpers for workflow API integration and RO-Crate packaging."""

import tempfile
import zipfile
from pathlib import Path

from config import (
    TEMPLATES_DIR,
    WORKFLOW_API_AUTH_HEADER,
    WORKFLOW_API_AUTH_SCHEME,
    WORKFLOW_API_KEY,
)


def build_rocrate_zip(context: dict) -> bytes:
    # Placeholder for template rendering with dynamic context in future.
    _ = context
    template_dir = TEMPLATES_DIR / "terrestrial-sdm"
    workflow_rendered = (template_dir / "workflow.yaml").read_text(encoding="utf-8")
    rocrate_rendered = (template_dir / "ro-crate-metadata.json").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        workflow_path = temp_path / "workflow.yaml"
        rocrate_path = temp_path / "ro-crate-metadata.json"
        workflow_path.write_text(workflow_rendered, encoding="utf-8")
        rocrate_path.write_text(rocrate_rendered, encoding="utf-8")

        zip_path = temp_path / "rocrate.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(workflow_path, arcname="workflow.yaml")
            zip_file.write(rocrate_path, arcname="ro-crate-metadata.json")

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            contents = [
                f"{info.filename} ({info.file_size} bytes)"
                for info in zip_file.infolist()
            ]
            print(f"RO-Crate contents: {contents}")

        return zip_path.read_bytes()


def build_workflow_api_headers() -> dict:
    headers = {}
    if WORKFLOW_API_KEY:
        if WORKFLOW_API_AUTH_SCHEME:
            headers[WORKFLOW_API_AUTH_HEADER] = (
                f"{WORKFLOW_API_AUTH_SCHEME} {WORKFLOW_API_KEY}"
            )
        else:
            headers[WORKFLOW_API_AUTH_HEADER] = WORKFLOW_API_KEY
    return headers
