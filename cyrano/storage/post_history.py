"""Audit trail of every reply posted to Reddit — Turso HTTP backend."""

import logging

from cyrano.storage.db import execute

logger = logging.getLogger(__name__)


def record_post(
    signal_id: str,
    project: str,
    post_url: str,
    comment_url: str,
    reply_text: str,
    action: str = "posted",
) -> None:
    """Append a post record to the audit log."""
    execute(
        """INSERT INTO post_history (signal_id, project, post_url, comment_url, reply_text, action)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [signal_id, project, post_url, comment_url, reply_text, action],
    )
    logger.info("Recorded post: %s → %s", signal_id, comment_url)


def load_post_history(date_str: str | None = None) -> list[dict]:
    """Load all post records for a given date (defaults to today)."""
    import datetime
    date_str = date_str or datetime.date.today().isoformat()

    return execute(
        "SELECT signal_id, project, post_url, comment_url, reply_text, action, posted_at FROM post_history WHERE date(posted_at) = ?",
        [date_str],
    )
