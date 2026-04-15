"""Checkpoint/resume system — Turso HTTP backend."""

import datetime
import json
import logging

from cyrano.storage.db import execute

logger = logging.getLogger(__name__)


def load_progress() -> dict:
    """Load today's progress, creating a fresh record if needed."""
    today = datetime.date.today().isoformat()

    rows = execute(
        "SELECT completed_subs, processed_ids, total_written FROM scan_progress WHERE date = ?",
        [today],
    )

    if rows:
        row = rows[0]
        return {
            "date": today,
            "completed_subs": set(json.loads(row["completed_subs"])),
            "processed_ids": set(json.loads(row["processed_ids"])),
            "total_written": row["total_written"],
        }

    return {
        "date": today,
        "completed_subs": set(),
        "processed_ids": set(),
        "total_written": 0,
    }


def save_progress(progress: dict) -> None:
    """Save progress checkpoint."""
    execute(
        """INSERT INTO scan_progress (date, completed_subs, processed_ids, total_written)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(date) DO UPDATE SET
               completed_subs = excluded.completed_subs,
               processed_ids = excluded.processed_ids,
               total_written = excluded.total_written""",
        [
            progress["date"],
            json.dumps(sorted(progress["completed_subs"])),
            json.dumps(sorted(progress["processed_ids"])),
            progress["total_written"],
        ],
    )
