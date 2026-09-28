"""Tests for feedback CSV export."""

import csv
from pathlib import Path

import database
from scripts.export_feedback import export_feedback


def test_export_feedback_writes_user_email_and_submission_fields(
    tmp_path: Path, monkeypatch
) -> None:
    """The export contains the reviewable feedback fields in stable order."""
    database_path = tmp_path / "bmd.db"
    output_path = tmp_path / "exports" / "feedback.csv"
    monkeypatch.setattr(database, "DATABASE_PATH", str(database_path))
    database.init_db()
    user_id = database.create_user("export@example.com", "hash", "Export User")
    database.create_feedback(user_id, "/results/example", "Helpful results page")

    assert export_feedback(database_path, output_path) == 1

    with output_path.open(encoding="utf-8", newline="") as output_file:
        rows = list(csv.DictReader(output_file))
    assert rows[0]["email"] == "export@example.com"
    assert rows[0]["page"] == "/results/example"
    assert rows[0]["message"] == "Helpful results page"
