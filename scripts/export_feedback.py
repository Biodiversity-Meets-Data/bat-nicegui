#!/usr/bin/env python3
"""Export stored user feedback to a CSV file.

Run with:
uv run python scripts/export_feedback.py --output feedback.csv

It uses DATABASE_PATH by default; override with:

uv run python scripts/export_feedback.py \
  --database /path/to/bmd.db \
  --output feedback.csv
"""

import argparse
import csv
import os
from pathlib import Path
import sqlite3

from dotenv import load_dotenv


FIELDNAMES = (
    "feedback_id",
    "user_id",
    "email",
    "page",
    "message",
    "created_at",
)


def export_feedback(database_path: Path, output_path: Path) -> int:
    """Write all feedback rows to CSV and return the number of rows exported."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT feedback_id, user_id, email, page, message, created_at
            FROM user_feedback
            ORDER BY created_at ASC, feedback_id ASC
            """
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=FIELDNAMES)
            writer.writeheader()
            count = 0
            for row in rows:
                writer.writerow({field: row[field] for field in FIELDNAMES})
                count += 1
            return count
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line options and environment-backed defaults."""
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.getenv("DATABASE_PATH", "/app/data/bmd.db")),
        help="SQLite database path (default: DATABASE_PATH or /app/data/bmd.db).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("feedback.csv"),
        help="CSV output path (default: feedback.csv).",
    )
    return parser.parse_args()


def main() -> None:
    """Export feedback using command-line settings."""
    args = parse_args()
    count = export_feedback(args.database, args.output)
    print(f"Exported {count} feedback entries to {args.output}")


if __name__ == "__main__":
    main()
