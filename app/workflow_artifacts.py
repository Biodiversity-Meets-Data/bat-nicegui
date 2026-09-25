"""Temporary workflow archive processing and persisted lightweight artifacts."""

import asyncio
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

import httpx

from config import (
    WORKFLOW_API_URL,
    WORKFLOW_ARTIFACT_CONCURRENCY,
    WORKFLOW_ARTIFACTS_DIR,
    WORKFLOW_ARTIFACT_MAX_BYTES,
)
from workflow_utils import build_workflow_api_headers

WORKFLOW_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ARTIFACTS_DIR = WORKFLOW_ARTIFACTS_DIR
MAX_ARCHIVE_BYTES = WORKFLOW_ARTIFACT_MAX_BYTES
EXTRACTION_CONCURRENCY = max(1, WORKFLOW_ARTIFACT_CONCURRENCY)
_EXTRACTION_SEMAPHORE = asyncio.Semaphore(EXTRACTION_CONCURRENCY)
_WORKFLOW_LOCKS: dict[str, asyncio.Lock] = {}


class WorkflowArtifactError(Exception):
    """Raised when workflow metadata or logs cannot be extracted."""


@dataclass(frozen=True, slots=True)
class WorkflowLog:
    """A persisted workflow-step log."""

    name: str
    path: Path


@dataclass(frozen=True, slots=True)
class StoredWorkflowArtifacts:
    """Persisted RO-Crate metadata and workflow logs."""

    metadata: dict[str, Any] | None
    logs: tuple[WorkflowLog, ...]


def workflow_artifact_directory(workflow_id: str) -> Path:
    """Return the validated artifact directory for a workflow."""

    if not WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
        raise WorkflowArtifactError("Invalid workflow ID")
    return ARTIFACTS_DIR / workflow_id


def _safe_log_name(name: str) -> str:
    """Convert an archive directory name into a safe log filename."""

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    return safe_name or "workflow-step"


def _metadata_entry(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return the root dataset entity from RO-Crate metadata."""

    graph = metadata.get("@graph")
    if not isinstance(graph, list):
        raise WorkflowArtifactError("RO-Crate metadata has no @graph")

    for entity in graph:
        if isinstance(entity, dict) and entity.get("@id") == "./":
            return entity
    raise WorkflowArtifactError("RO-Crate metadata has no root dataset")


def _log_archive_entries(archive: ZipFile) -> list[tuple[str, str]]:
    """Return archive log paths and their unique persisted names."""

    entries: list[tuple[str, str]] = []
    used_names: set[str] = set()
    for info in archive.infolist():
        path = Path(info.filename)
        if path.name != "main.log" or info.is_dir():
            continue
        parent_name = _safe_log_name(path.parent.name)
        log_name = f"{parent_name}.log"
        suffix = 2
        while log_name in used_names:
            log_name = f"{parent_name}-{suffix}.log"
            suffix += 1
        used_names.add(log_name)
        entries.append((info.filename, log_name))
    return entries


def _extract_archive(archive_path: Path, workflow_id: str) -> None:
    """Extract metadata and logs into the workflow-specific directory."""

    destination = workflow_artifact_directory(workflow_id)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{workflow_id}-", dir=ARTIFACTS_DIR))
    try:
        metadata_bytes: bytes | None = None
        with ZipFile(archive_path) as archive:
            for info in archive.infolist():
                if (
                    not info.is_dir()
                    and Path(info.filename).name == "ro-crate-metadata.json"
                ):
                    metadata_bytes = archive.read(info)
                    break

            if metadata_bytes is None:
                raise WorkflowArtifactError("RO-Crate metadata is missing")

            try:
                metadata = json.loads(metadata_bytes)
            except json.JSONDecodeError as exc:
                raise WorkflowArtifactError(
                    "RO-Crate metadata is invalid JSON"
                ) from exc
            if not isinstance(metadata, dict):
                raise WorkflowArtifactError("RO-Crate metadata must be a JSON object")
            _metadata_entry(metadata)

            (staging / "logs").mkdir()
            (staging / "ro-crate-metadata.json").write_bytes(metadata_bytes)
            for archive_name, log_name in _log_archive_entries(archive):
                (staging / "logs" / log_name).write_bytes(archive.read(archive_name))

        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
    except (BadZipFile, OSError) as exc:
        raise WorkflowArtifactError(
            "Workflow result archive could not be read"
        ) from exc
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


async def extract_workflow_artifacts(workflow_id: str) -> None:
    """Download a workflow ZIP temporarily and persist only metadata and logs."""

    directory = workflow_artifact_directory(workflow_id)
    lock = _WORKFLOW_LOCKS.setdefault(workflow_id, asyncio.Lock())
    async with lock:
        if (directory / "ro-crate-metadata.json").is_file():
            return

        async with _EXTRACTION_SEMAPHORE:
            ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
            archive_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=f"{workflow_id}-", suffix=".zip", delete=False
                ) as archive_file:
                    archive_path = Path(archive_file.name)
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        async with client.stream(
                            "GET",
                            f"{WORKFLOW_API_URL}/{workflow_id}/download",
                            headers=build_workflow_api_headers(),
                        ) as response:
                            response.raise_for_status()
                            total_bytes = 0
                            async for chunk in response.aiter_bytes():
                                total_bytes += len(chunk)
                                if total_bytes > MAX_ARCHIVE_BYTES:
                                    raise WorkflowArtifactError(
                                        "Workflow result archive is too large"
                                    )
                                archive_file.write(chunk)
                await asyncio.to_thread(_extract_archive, archive_path, workflow_id)
            except httpx.HTTPError as exc:
                raise WorkflowArtifactError(
                    "Workflow result archive could not be downloaded"
                ) from exc
            finally:
                if archive_path is not None:
                    archive_path.unlink(missing_ok=True)


def load_workflow_artifacts(workflow_id: str) -> StoredWorkflowArtifacts:
    """Load persisted metadata and logs for a workflow."""

    directory = workflow_artifact_directory(workflow_id)
    metadata: dict[str, Any] | None = None
    metadata_path = directory / "ro-crate-metadata.json"
    if metadata_path.is_file():
        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            metadata = loaded

    logs_directory = directory / "logs"
    logs = tuple(
        WorkflowLog(path.name.removesuffix(".log"), path)
        for path in sorted(logs_directory.glob("*.log"))
        if path.is_file()
    )
    return StoredWorkflowArtifacts(metadata, logs)


def delete_workflow_artifacts(workflow_id: str) -> None:
    """Delete all persisted artifacts for a workflow, if present."""

    directory = workflow_artifact_directory(workflow_id)
    if directory.exists():
        shutil.rmtree(directory)
