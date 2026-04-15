"""Turso HTTP API client + schema bootstrap.

Uses Turso's pipeline API directly via requests — no native dependencies.
"""

import json
import logging

import requests

from cyrano.config import TURSO_URL, TURSO_AUTH_TOKEN

logger = logging.getLogger(__name__)

_initialized = False

SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS signals (
        id TEXT PRIMARY KEY,
        project TEXT NOT NULL,
        platform TEXT NOT NULL,
        platform_id TEXT NOT NULL,
        url TEXT NOT NULL,
        title TEXT NOT NULL,
        body TEXT,
        author TEXT,
        subreddit TEXT,
        score INTEGER DEFAULT 0,
        reply_count INTEGER DEFAULT 0,
        created_utc REAL,
        status TEXT,
        analysis TEXT,
        scanned_at TEXT NOT NULL DEFAULT (date('now'))
    )""",
    "CREATE INDEX IF NOT EXISTS idx_signals_scanned_at ON signals(scanned_at)",
    """CREATE TABLE IF NOT EXISTS approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL,
        project TEXT,
        decision TEXT NOT NULL,
        edited_text TEXT,
        telegram_message_id INTEGER,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS post_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_id TEXT NOT NULL,
        project TEXT,
        post_url TEXT,
        comment_url TEXT,
        reply_text TEXT,
        action TEXT,
        posted_at TEXT DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS scan_progress (
        date TEXT PRIMARY KEY DEFAULT (date('now')),
        completed_subs TEXT DEFAULT '[]',
        processed_ids TEXT DEFAULT '[]',
        total_written INTEGER DEFAULT 0
    )""",
]


def _get_http_url() -> str:
    """Convert libsql:// URL to https:// for the HTTP API."""
    url = TURSO_URL
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://", 1)
    return url


def _execute_pipeline(statements: list[dict]) -> list[dict]:
    """Send a batch of statements to Turso's pipeline API."""
    url = f"{_get_http_url()}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }

    requests_body = []
    for stmt in statements:
        requests_body.append({"type": "execute", "stmt": stmt})
    requests_body.append({"type": "close"})

    resp = requests.post(url, headers=headers, json={"requests": requests_body}, timeout=30)
    if resp.status_code != 200:
        logger.error("Turso HTTP %d: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()
    data = resp.json()

    results = data.get("results", [])
    for i, result in enumerate(results):
        if result.get("type") == "error":
            error = result.get("error", {})
            raise RuntimeError(f"Turso error on statement {i}: {error.get('message', error)}")

    return results


def execute(sql: str, args: list | None = None) -> list[dict]:
    """Execute a single SQL statement. Returns rows as list of dicts."""
    _ensure_schema()

    stmt = {"sql": sql}
    if args:
        stmt["args"] = [_to_turso_arg(a) for a in args]

    results = _execute_pipeline([stmt])

    # Parse the first result
    if not results or results[0].get("type") != "ok":
        return []

    response = results[0].get("response", {})
    result = response.get("result", {})
    cols = [c["name"] for c in result.get("cols", [])]
    rows = []
    for row in result.get("rows", []):
        rows.append(dict(zip(cols, [_from_turso_value(v) for v in row])))
    return rows


def execute_many(statements: list[tuple[str, list | None]]) -> None:
    """Execute multiple SQL statements in a single pipeline call."""
    _ensure_schema()

    stmts = []
    for sql, args in statements:
        stmt = {"sql": sql}
        if args:
            stmt["args"] = [_to_turso_arg(a) for a in args]
        stmts.append(stmt)

    _execute_pipeline(stmts)


def _to_turso_arg(value) -> dict:
    """Convert a Python value to a Turso typed argument."""
    if value is None:
        return {"type": "null", "value": None}
    elif isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    elif isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    elif isinstance(value, float):
        return {"type": "float", "value": value}
    else:
        return {"type": "text", "value": str(value)}


def _from_turso_value(v: dict):
    """Convert a Turso typed value back to Python."""
    if v is None or v.get("type") == "null":
        return None
    t = v.get("type", "text")
    val = v.get("value")
    if t == "integer":
        return int(val)
    elif t == "float":
        return float(val)
    return val


def _ensure_schema():
    """Bootstrap tables on first call."""
    global _initialized
    if _initialized:
        return

    if not TURSO_URL or not TURSO_AUTH_TOKEN:
        raise RuntimeError("TURSO_URL and TURSO_AUTH_TOKEN must be set in .env")

    stmts = [{"sql": s} for s in SCHEMA_STATEMENTS]
    _execute_pipeline(stmts)
    _initialized = True
    logger.info("Turso schema bootstrapped: %s", TURSO_URL)
