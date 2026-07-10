"""
Database module for BMD application
SQLite database with users and workflows tables
"""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/bmd.db")


class DatabaseError(Exception):
    """Base class for errors raised by a database operation."""


class UserNotFoundError(DatabaseError):
    """Raised when a database operation targets a user_id that does not exist."""

    def __init__(self, user_id: str) -> None:
        super().__init__(f"No user found with user_id={user_id!r}")
        self.user_id = user_id


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create users table with user_id as primary key
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            orcid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add orcid column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN orcid TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create workflows table with workflow_id and user_id as foreign key
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
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
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)

    # Add ecosystem_type column if it doesn't exist (for existing databases)
    try:
        cursor.execute(
            'ALTER TABLE workflows ADD COLUMN ecosystem_type TEXT DEFAULT "terrestrial"'
        )
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add species_name column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE workflows ADD COLUMN species_name TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add geometry_wkt column if it doesn't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE workflows ADD COLUMN geometry_wkt TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create indexes for better query performance
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    conn.commit()
    conn.close()
    print("Database initialized successfully")


def create_user(
    email: str, password_hash: str, name: str, orcid: Optional[str] = None
) -> str:
    """Create a new user and return the user_id"""
    conn = get_connection()
    cursor = conn.cursor()

    user_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO users (user_id, email, password_hash, name, orcid)
        VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, email, password_hash, name, orcid),
    )

    conn.commit()
    conn.close()

    return user_id


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by user_id"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


@contextmanager
def get_cursor():
    """Yield a new cursor to a database.

    * On context manager entry: yield a new database cursor.
    * On context manager exit: try to commit the changes to the database,
      roll back the changes on error. Always close the connection.
    """
    conn = get_connection()
    try:
        yield conn.cursor()
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise DatabaseError(str(e)) from e
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_user_profile(user_id: str, name: str, email: str, orcid: str) -> None:
    """Update a user's profile data in the application's database.

    Raises:
        UserNotFoundError: if no user exists with the given user_id.
    """

    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET name = ?, email = ?, orcid = ?, updated_at = ? "
            "WHERE user_id = ?",
            (
                name,
                email,
                orcid or None,
                datetime.now(timezone.utc).isoformat(),
                user_id,
            ),
        )
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)


def update_user_password(user_id: str, password_hash: str) -> None:
    """Update a user's password hash.

    Raises:
        UserNotFoundError: if no user exists with the given user_id.
    """

    with get_cursor() as cursor:
        cursor.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
            (password_hash, datetime.now(timezone.utc).isoformat(), user_id),
        )
        if cursor.rowcount == 0:
            raise UserNotFoundError(user_id)


def delete_user(user_id: str) -> bool:
    """Delete a user and all their workflows"""
    conn = get_connection()
    cursor = conn.cursor()

    # Delete user's workflows first
    cursor.execute("DELETE FROM workflows WHERE user_id = ?", (user_id,))

    # Delete the user
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def check_email_exists(email: str, exclude_user_id: Optional[str] = None) -> bool:
    """Check if email exists, optionally excluding a specific user"""
    conn = get_connection()
    cursor = conn.cursor()

    if exclude_user_id:
        cursor.execute(
            "SELECT 1 FROM users WHERE email = ? AND user_id != ?",
            (email, exclude_user_id),
        )
    else:
        cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))

    exists = cursor.fetchone() is not None
    conn.close()

    return exists


def create_workflow(
    workflow_id: str,
    user_id: str,
    name: str,
    description: str,
    species_name: str,
    ecosystem_type: str,
    geometry_type: str,
    geometry_wkt: str,
    parameters: str,
    status: str = "submitted",
) -> str:
    """Create a new workflow"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO workflows (
            workflow_id, user_id, name, description, species_name,
            ecosystem_type, geometry_type,
            geometry_wkt, parameters, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            workflow_id,
            user_id,
            name,
            description,
            species_name,
            ecosystem_type,
            geometry_type,
            geometry_wkt,
            parameters,
            status,
        ),
    )

    conn.commit()
    conn.close()

    return workflow_id


def get_user_workflows(user_id: str) -> List[Dict]:
    """Get all workflows for a user"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM workflows 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    """,
        (user_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_workflow_by_id(workflow_id: str) -> Optional[Dict]:
    """Get a specific workflow by ID"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def update_workflow_status(
    workflow_id: str,
    status: str,
    results: Optional[str] = None,
    error: Optional[str] = None,
):
    """Update workflow status and optionally results or error"""
    conn = get_connection()
    cursor = conn.cursor()

    update_fields = ["status = ?", "updated_at = ?"]
    params = [status, datetime.now(timezone.utc).isoformat()]

    if status == "completed":
        update_fields.append("completed_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())

    if results:
        update_fields.append("results = ?")
        params.append(results)

    if error:
        update_fields.append("error_message = ?")
        params.append(error)

    params.append(workflow_id)

    query = f"UPDATE workflows SET {', '.join(update_fields)} WHERE workflow_id = ?"
    cursor.execute(query, params)

    conn.commit()
    conn.close()


def delete_workflow(workflow_id: str) -> bool:
    """Delete a workflow by ID"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM workflows WHERE workflow_id = ?", (workflow_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def get_all_workflows_by_status(status: str) -> List[Dict]:
    """Get all workflows with a specific status (admin use)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT w.*, u.email, u.name as user_name
        FROM workflows w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.status = ?
        ORDER BY w.created_at DESC
        """,
        (status,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]
