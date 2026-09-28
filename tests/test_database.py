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
    feedback_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(user_feedback)")
    }
    assert feedback_columns == {
        "feedback_id",
        "user_id",
        "email",
        "page",
        "message",
        "created_at",
    }
    connection.close()


def test_feedback_is_stored_validated_and_deleted_with_user(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "bmd.db"
    monkeypatch.setattr(database, "DATABASE_PATH", str(db_path))
    database.init_db()

    user_id = database.create_user("feedback@example.com", "hash", "Feedback User")
    feedback_id = database.create_feedback(
        user_id,
        "/workflows",
        "  The workflow page is clear.  ",
    )

    connection = sqlite3.connect(db_path)
    feedback = connection.execute(
        "SELECT feedback_id, user_id, email, page, message, created_at "
        "FROM user_feedback WHERE feedback_id = ?",
        (feedback_id,),
    ).fetchone()
    assert feedback[:5] == (
        feedback_id,
        user_id,
        "feedback@example.com",
        "/workflows",
        "The workflow page is clear.",
    )
    assert feedback[4]
    connection.close()

    import pytest

    with pytest.raises(ValueError, match="required"):
        database.create_feedback(user_id, "/workflows", "   ")
    with pytest.raises(ValueError, match="2000"):
        database.create_feedback(user_id, "/workflows", "x" * 2001)

    assert database.delete_user(user_id)
    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT COUNT(*) FROM user_feedback").fetchone()[0] == 0
    connection.close()
