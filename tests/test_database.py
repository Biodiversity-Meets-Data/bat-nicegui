"""Tests for workflow database migrations."""

import sqlite3

import database


def test_init_db_migrates_existing_workflows_table(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "bmd.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE workflows (
            workflow_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            species_name TEXT,
            ecosystem_type TEXT,
            geometry_type TEXT,
            geometry_wkt TEXT,
            parameters TEXT,
            status TEXT DEFAULT 'submitted',
            results TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
        """
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_db()

    connection = sqlite3.connect(db_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(workflows)")}
    assert "bat_name" in columns
    assert "species_name" in columns
    assert "species_col_id" in columns
    assert "parameter_metadata" in columns
    assert "artifact_status" in columns
    assert "artifact_extracted_at" in columns
    assert "artifact_error" in columns
    connection.close()
