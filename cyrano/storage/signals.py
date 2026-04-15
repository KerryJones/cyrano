"""Signal storage — Turso HTTP backend."""

import datetime
import json
import logging

from cyrano.storage.db import execute

logger = logging.getLogger(__name__)


def save_signals(signals: list[dict], date_str: str | None = None) -> None:
    """Upsert signals into the database."""
    if not signals:
        return

    date_str = date_str or datetime.date.today().isoformat()

    for s in signals:
        execute(
            """INSERT OR IGNORE INTO signals
               (id, project, platform, platform_id, url, title, body, author,
                subreddit, score, reply_count, created_utc, status, analysis, scanned_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                s["id"], s.get("project", ""), s["platform"], s["platform_id"],
                s["url"], s["title"], s.get("body", ""), s.get("author", ""),
                s.get("subreddit", ""), s.get("score", 0), s.get("reply_count", 0),
                s.get("created_utc", 0), s.get("status", ""),
                json.dumps(s.get("analysis", {})), date_str,
            ],
        )

    logger.info("Saved %d signals to Turso", len(signals))


def load_signals(date_str: str | None = None) -> list[dict]:
    """Load signals for a given date."""
    date_str = date_str or datetime.date.today().isoformat()

    rows = execute("SELECT * FROM signals WHERE scanned_at = ?", [date_str])

    for row in rows:
        if isinstance(row.get("analysis"), str):
            row["analysis"] = json.loads(row["analysis"])
    return rows


def load_recent_signal_ids(lookback_days: int = 3) -> set[str]:
    """Load signal IDs from recent days for deduplication."""
    cutoff = (datetime.date.today() - datetime.timedelta(days=lookback_days)).isoformat()

    rows = execute("SELECT id FROM signals WHERE scanned_at >= ?", [cutoff])
    return {row["id"] for row in rows}
