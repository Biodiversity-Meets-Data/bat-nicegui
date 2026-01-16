"""
Database module for BMD application
SQLite database with users and workflows tables
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional, List, Dict
import os

DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/data/bmd.db")


def get_connection():
    """Get a database connection with row factory"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create users table with user_id as primary key
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            orcid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add orcid column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN orcid TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create workflows table with workflow_id and user_id as foreign key
    cursor.execute('''
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
    ''')

    # Add ecosystem_type column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE workflows ADD COLUMN ecosystem_type TEXT DEFAULT "terrestrial"')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Add species_name column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE workflows ADD COLUMN species_name TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Add geometry_wkt column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE workflows ADD COLUMN geometry_wkt TEXT')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Create indexes for better query performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON workflows(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")


def create_user(email: str, password_hash: str, name: str, orcid: Optional[str] = None) -> str:
    """Create a new user and return the user_id"""
    conn = get_connection()
    cursor = conn.cursor()
    
    user_id = str(uuid.uuid4())
    
    cursor.execute('''
        INSERT INTO users (user_id, email, password_hash, name, orcid)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, email, password_hash, name, orcid))
    
    conn.commit()
    conn.close()
    
    return user_id


def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_user_by_id(user_id: str) -> Optional[Dict]:
    """Get user by user_id"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def update_user(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    orcid: Optional[str] = None,
    password_hash: Optional[str] = None
) -> bool:
    """Update user details"""
    conn = get_connection()
    cursor = conn.cursor()
    
    update_fields = ['updated_at = ?']
    params = [datetime.utcnow().isoformat()]
    
    if name is not None:
        update_fields.append('name = ?')
        params.append(name)
    
    if email is not None:
        update_fields.append('email = ?')
        params.append(email)
    
    if orcid is not None:
        update_fields.append('orcid = ?')
        params.append(orcid if orcid else None)
    
    if password_hash is not None:
        update_fields.append('password_hash = ?')
        params.append(password_hash)
    
    params.append(user_id)
    
    query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
    cursor.execute(query, params)
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated


def delete_user(user_id: str) -> bool:
    """Delete a user and all their workflows"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete user's workflows first
    cursor.execute('DELETE FROM workflows WHERE user_id = ?', (user_id,))
    
    # Delete the user
    cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted


def check_email_exists(email: str, exclude_user_id: Optional[str] = None) -> bool:
    """Check if email exists, optionally excluding a specific user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if exclude_user_id:
        cursor.execute('SELECT 1 FROM users WHERE email = ? AND user_id != ?', (email, exclude_user_id))
    else:
        cursor.execute('SELECT 1 FROM users WHERE email = ?', (email,))
    
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
    status: str = 'submitted'
) -> str:
    """Create a new workflow"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO workflows (
            workflow_id, user_id, name, description, species_name,
            ecosystem_type, geometry_type,
            geometry_wkt, parameters, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        workflow_id, user_id, name, description, species_name,
        ecosystem_type, geometry_type, geometry_wkt, parameters, status
    ))
    
    conn.commit()
    conn.close()
    
    return workflow_id


def get_user_workflows(user_id: str) -> List[Dict]:
    """Get all workflows for a user"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM workflows 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def get_workflow_by_id(workflow_id: str) -> Optional[Dict]:
    """Get a specific workflow by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM workflows WHERE workflow_id = ?', (workflow_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def update_workflow_status(
    workflow_id: str, 
    status: str, 
    results: Optional[str] = None,
    error: Optional[str] = None
):
    """Update workflow status and optionally results or error"""
    conn = get_connection()
    cursor = conn.cursor()
    
    update_fields = ['status = ?', 'updated_at = ?']
    params = [status, datetime.utcnow().isoformat()]
    
    if status == 'completed':
        update_fields.append('completed_at = ?')
        params.append(datetime.utcnow().isoformat())
    
    if results:
        update_fields.append('results = ?')
        params.append(results)
    
    if error:
        update_fields.append('error_message = ?')
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
    
    cursor.execute('DELETE FROM workflows WHERE workflow_id = ?', (workflow_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted


def get_all_workflows_by_status(status: str) -> List[Dict]:
    """Get all workflows with a specific status (admin use)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT w.*, u.email, u.name as user_name
        FROM workflows w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.status = ?
        ORDER BY w.created_at DESC
    ''', (status,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
