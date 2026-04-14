"""Audit trail of every reply posted to Reddit."""

import datetime
import json
import logging
from pathlib import Path

from cyrano.config import DATA_DIR

logger = logging.getLogger(__name__)

POST_HISTORY_DIR = DATA_DIR / "post_history"


def _ensure_dir():
    POST_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def record_post(
    signal_id: str,
    project: str,
    post_url: str,
    comment_url: str,
    reply_text: str,
    action: str = "posted",
) -> None:
    """Append a post record to today's audit log."""
    _ensure_dir()
    date_str = datetime.date.today().isoformat()
    filepath = POST_HISTORY_DIR / f"{date_str}.json"

    records = []
    if filepath.exists():
        with open(filepath) as f:
            records = json.load(f)

    records.append({
        "signal_id": signal_id,
        "project": project,
        "post_url": post_url,
        "comment_url": comment_url,
        "reply_text": reply_text,
        "action": action,
        "posted_at": datetime.datetime.utcnow().isoformat(),
    })

    with open(filepath, "w") as f:
        json.dump(records, f, indent=2, default=str)

    logger.info("Recorded post: %s → %s", signal_id, comment_url)


def load_post_history(date_str: str | None = None) -> list[dict]:
    """Load all post records for a given date (defaults to today)."""
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    filepath = POST_HISTORY_DIR / f"{date_str}.json"
    if not filepath.exists():
        return []
    with open(filepath) as f:
        return json.load(f)
