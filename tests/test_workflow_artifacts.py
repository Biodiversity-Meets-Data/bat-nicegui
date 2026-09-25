import json
import zipfile
from pathlib import Path

import pytest

import workflow_artifacts


def _write_fixture_zip(path: Path) -> None:
    metadata = {
        "@context": ["https://w3id.org/ro/crate/1.2-DRAFT/context"],
        "@graph": [{"@id": "./", "@type": "Dataset", "name": "Test workflow"}],
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("ro-crate-metadata.json", json.dumps(metadata))
        archive.writestr("download-step/main.log", "download complete\n")
        archive.writestr("run-step/main.log", "model complete\n")
        archive.writestr("outputs/results.tif", "large output placeholder")


def test_extract_archive_persists_only_metadata_and_logs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_path = tmp_path / "results.zip"
    _write_fixture_zip(archive_path)
    artifact_root = tmp_path / "workflow-artifacts"
    monkeypatch.setattr(workflow_artifacts, "ARTIFACTS_DIR", artifact_root)

    workflow_artifacts._extract_archive(archive_path, "workflow-123")

    workflow_dir = artifact_root / "workflow-123"
    assert (workflow_dir / "ro-crate-metadata.json").is_file()
    assert (workflow_dir / "logs" / "download-step.log").read_text() == (
        "download complete\n"
    )
    assert (workflow_dir / "logs" / "run-step.log").read_text() == "model complete\n"
    assert not (workflow_dir / "outputs").exists()


def test_load_and_delete_workflow_artifacts(tmp_path: Path, monkeypatch) -> None:
    artifact_root = tmp_path / "workflow-artifacts"
    monkeypatch.setattr(workflow_artifacts, "ARTIFACTS_DIR", artifact_root)
    archive_path = tmp_path / "results.zip"
    _write_fixture_zip(archive_path)
    workflow_artifacts._extract_archive(archive_path, "workflow-123")

    artifacts = workflow_artifacts.load_workflow_artifacts("workflow-123")
    assert artifacts.metadata is not None
    assert [log.name for log in artifacts.logs] == ["download-step", "run-step"]

    workflow_artifacts.delete_workflow_artifacts("workflow-123")
    workflow_artifacts.delete_workflow_artifacts("workflow-123")
    assert not (artifact_root / "workflow-123").exists()


@pytest.mark.parametrize("workflow_id", ["../escape", "/absolute", "", "a/b"])
def test_workflow_artifact_directory_rejects_unsafe_ids(workflow_id: str) -> None:
    with pytest.raises(workflow_artifacts.WorkflowArtifactError):
        workflow_artifacts.workflow_artifact_directory(workflow_id)
