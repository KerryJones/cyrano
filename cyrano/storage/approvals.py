"""Approval decision persistence — Turso HTTP backend."""

import logging

from cyrano.storage.db import execute

logger = logging.getLogger(__name__)


def save_approval(
    signal_id: str,
    decision: str,
    project: str = "",
    edited_text: str | None = None,
    telegram_message_id: int | None = None,
) -> None:
    """Persist an approval decision. Updates if signal_id already exists."""
    existing = execute("SELECT id FROM approvals WHERE signal_id = ?", [signal_id])

    if existing:
        execute(
            """UPDATE approvals
               SET decision = ?, edited_text = ?, telegram_message_id = ?,
                   updated_at = datetime('now')
               WHERE signal_id = ?""",
            [decision, edited_text, telegram_message_id, signal_id],
        )
    else:
        execute(
            """INSERT INTO approvals (signal_id, project, decision, edited_text, telegram_message_id)
               VALUES (?, ?, ?, ?, ?)""",
            [signal_id, project, decision, edited_text, telegram_message_id],
        )


def get_approval(signal_id: str) -> dict | None:
    """Look up the approval record for a signal."""
    rows = execute(
        "SELECT signal_id, project, decision, edited_text, telegram_message_id, created_at, updated_at FROM approvals WHERE signal_id = ?",
        [signal_id],
    )
    return rows[0] if rows else None


def load_approvals(date_str: str | None = None) -> list[dict]:
    """Load all approval records for a given date (defaults to today)."""
    import datetime
    date_str = date_str or datetime.date.today().isoformat()

    return execute(
        "SELECT signal_id, project, decision, edited_text, telegram_message_id, created_at, updated_at FROM approvals WHERE date(created_at) = ?",
        [date_str],
    )
