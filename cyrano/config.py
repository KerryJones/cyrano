"""Configuration loader for Cyrano.

Loads settings from .env and YAML config files.
Supports multiple projects via config/projects/{name}/ directories.
"""

import os
import sys
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Root directory of the project (where pyproject.toml lives)
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
PROJECTS_DIR = CONFIG_DIR / "projects"

load_dotenv(ROOT_DIR / ".env")


def _require_env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        sys.exit(f"ERROR: Set {key} in .env")
    return val


# Anthropic / LLM settings
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
LLM_SCORING_MODEL = os.environ.get("LLM_SCORING_MODEL", "anthropic/claude-haiku-4-5")
LLM_DRAFTING_MODEL = os.environ.get("LLM_DRAFTING_MODEL", "anthropic/claude-sonnet-4-6")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "1024"))

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Reddit (read-only scanner — no auth needed)
REDDIT_HEADERS = {
    "User-Agent": "Cyrano/0.1 (value-first community reply assistant)"
}
REDDIT_SLEEP = 2  # seconds between Reddit API requests

# Reddit (PRAW — for posting replies)
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD = os.environ.get("REDDIT_PASSWORD", "")

# Turso (libSQL)
TURSO_URL = os.environ.get("TURSO_URL", "")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

# Scheduler
SCAN_CRON = os.environ.get("SCAN_CRON", "*/30 8-20 * * *")
TIMEZONE = os.environ.get("TIMEZONE", "America/New_York")


def load_yaml(filename: str, directory: Path | None = None) -> dict | list:
    """Load a YAML file from the given directory (defaults to CONFIG_DIR)."""
    if directory is None:
        directory = CONFIG_DIR
    filepath = directory / filename
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        return yaml.safe_load(f) or {}


def list_projects() -> list[str]:
    """Return project names in scan order. Uses config/projects.yml if present."""
    projects_file = CONFIG_DIR / "projects.yml"
    if projects_file.exists():
        ordered = load_yaml("projects.yml")
        if isinstance(ordered, list) and ordered:
            return ordered
    if not PROJECTS_DIR.exists():
        return ["default"]
    dirs = [d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()]
    return dirs if dirs else ["default"]


def load_project_config(project: str) -> tuple[dict, list[str], dict]:
    """Load (personality, subreddits, filters) for a named project.

    Falls back to top-level config/ files when no projects/ directory exists.
    """
    project_dir = PROJECTS_DIR / project
    if project_dir.exists():
        directory = project_dir
    else:
        directory = CONFIG_DIR

    personality = load_yaml("personality.yml", directory=directory)
    raw_subs = load_yaml("subreddits.yml", directory=directory)
    filters = load_yaml("filters.yml", directory=directory)

    if not isinstance(raw_subs, list):
        raw_subs = []
    return personality, raw_subs, filters


def load_subreddits(filename: str = "subreddits.yml") -> list[str]:
    subs = load_yaml(filename)
    if not subs or not isinstance(subs, list):
        raise ValueError(f"No subreddits found in {filename}")
    return subs


def load_personality(filename: str = "personality.yml") -> dict:
    return load_yaml(filename) or {}


def load_filters(filename: str = "filters.yml") -> dict:
    return load_yaml(filename) or {}


def get_max_post_age_hours(filters: dict) -> int:
    return filters.get("thresholds", {}).get("max_age_hours", 24)


def ensure_data_dirs():
    """Legacy — no longer needed with Turso backend. Kept for compatibility."""
    pass
