"""Approval decision persistence — daily JSON files matching signals.py pattern."""

import datetime
import json
import logging
from pathlib import Path

from cyrano.config import DATA_DIR

logger = logging.getLogger(__name__)

APPROVALS_DIR = DATA_DIR / "approvals"


def _ensure_dir():
    APPROVALS_DIR.mkdir(parents=True, exist_ok=True)


def _today_file() -> Path:
    return APPROVALS_DIR / f"{datetime.date.today().isoformat()}.json"


def _load_file(filepath: Path) -> list[dict]:
    if not filepath.exists():
        return []
    with open(filepath) as f:
        return json.load(f)


def save_approval(
    signal_id: str,
    decision: str,
    project: str = "",
    edited_text: str | None = None,
    telegram_message_id: int | None = None,
) -> None:
    """Persist an approval decision (approved/edited/skipped/posted)."""
    _ensure_dir()
    filepath = _today_file()
    records = _load_file(filepath)

    # Update existing record if present, otherwise append
    for record in records:
        if record.get("signal_id") == signal_id:
            record.update({
                "decision": decision,
                "edited_text": edited_text,
                "telegram_message_id": telegram_message_id,
                "updated_at": datetime.datetime.utcnow().isoformat(),
            })
            break
    else:
        records.append({
            "signal_id": signal_id,
            "project": project,
            "decision": decision,
            "edited_text": edited_text,
            "telegram_message_id": telegram_message_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "updated_at": datetime.datetime.utcnow().isoformat(),
        })

    with open(filepath, "w") as f:
        json.dump(records, f, indent=2, default=str)


def get_approval(signal_id: str) -> dict | None:
    """Look up today's approval record for a signal."""
    for record in _load_file(_today_file()):
        if record.get("signal_id") == signal_id:
            return record
    return None


def load_approvals(date_str: str | None = None) -> list[dict]:
    """Load all approval records for a given date (defaults to today)."""
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    return _load_file(APPROVALS_DIR / f"{date_str}.json")
