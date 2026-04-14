# Architecture

## Overview

Cyrano is a Python CLI app that monitors Reddit for relevant conversations, drafts value-first replies using a two-pass LLM strategy, and sends candidates to Telegram for human approval before posting via PRAW.

Forked from [OutreachPilot](https://github.com/sausi-7/reddit-outreach). Google Sheets export replaced with Telegram approval flow, OpenAI replaced with Claude via LiteLLM, multi-project support added.

## Pipeline

```
config/projects/{name}/ → personality.yml, subreddits.yml, filters.yml
         │
         ▼
┌─ Reddit Scanner (scanners/reddit.py) ─────────────────────┐
│  Fetches /r/{sub}/new.json via public API (no auth)        │
│  Rate-limited: 2s between requests, exponential backoff    │
└────────────────────────────────────────────────────────────┘
         │ list[RawSignal]
         ▼
┌─ Pre-filter (filters/rule_filter.py) ─────────────────────┐
│  Keywords, score, age, flairs, post type, status           │
│  Zero AI cost — eliminates ~80% of signals                 │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Dedup (filters/dedup.py) ────────────────────────────────┐
│  Cross-day deduplication via data/signals/ JSON files      │
│  3-day lookback window                                     │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Two-Pass LLM Analysis (analyzers/pipeline.py) ───────────┐
│  Pass 1 (Haiku — cheap): Yes/Maybe/No + why                │
│  Pass 2 (Sonnet — quality): full reply draft                │
│  Only Yes/Maybe signals reach Pass 2                        │
│  LLM calls via LiteLLM (analyzers/llm_client.py)           │
└────────────────────────────────────────────────────────────┘
         │ list[ScoredSignal]
         ▼
┌─ Telegram Bot (telegram/bot.py) ──────────────────────────┐
│  Sends MarkdownV2 card with inline keyboard:               │
│  [Approve] [Edit] [Skip] [No Plug]                         │
│  Edit: ConversationHandler waits for user reply text        │
│  Approve/Edit → RedditPoster → update card with link       │
└────────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Reddit Poster (reddit/poster.py) ────────────────────────┐
│  PRAW script-type app, posts from user's account           │
│  120s minimum gap between posts (rate limiting)            │
│  Checks locked/archived before posting                     │
└────────────────────────────────────────────────────────────┘
```

## Module Map

| Module | Purpose |
|--------|---------|
| `__main__.py` | CLI: `scan`, `run`, `bot` commands |
| `pipeline.py` | `run_scan(project)` — orchestrates the full pipeline |
| `models.py` | `ScoredSignal` dataclass (signal + analysis + approval state) |
| `config.py` | Loads .env + YAML configs, multi-project support |
| `scheduler.py` | `CyranoScheduler` — APScheduler AsyncIOScheduler with CronTrigger |
| `scanners/base.py` | `RawSignal`, `Reply` dataclasses, `Scanner` protocol, `fetch_json` |
| `scanners/reddit.py` | `RedditScanner` — fetches /new.json + comment threads |
| `analyzers/pipeline.py` | Two-pass: `_score_signal()` (Haiku) + `_draft_reply()` (Sonnet) |
| `analyzers/llm_client.py` | `chat_completion()` — LiteLLM wrapper with retry + JSON parsing |
| `analyzers/base.py` | `Analysis` dataclass |
| `telegram/bot.py` | `CyranoBot` — send candidates, handle callbacks, post replies |
| `telegram/formatter.py` | `format_candidate()`, `format_status_update()`, MarkdownV2 escaping |
| `reddit/poster.py` | `RedditPoster` — PRAW posting with rate limiting |
| `filters/rule_filter.py` | `apply_pre_filters()` — zero-cost keyword/score/age filtering |
| `filters/dedup.py` | `deduplicate_signals()` — cross-day dedup via signal ID history |
| `personas/prompt_builder.py` | Builds personality + AI prefs blocks for LLM prompts |
| `storage/signals.py` | Daily JSON signal persistence + dedup ID lookback |
| `storage/approvals.py` | Daily JSON approval decision records |
| `storage/post_history.py` | Audit trail of every posted Reddit comment |
| `storage/progress.py` | Checkpoint/resume — completed subs + processed IDs, daily reset |

## Multi-Project Config

```
config/projects/
├── matcha/          # Matcha Match — tea/cafe communities
├── rowcraft/        # RowCraft — rowing/fitness communities
└── dealcred/        # DealCred — real estate investing communities
```

Each project directory contains `personality.yml`, `subreddits.yml`, `filters.yml`. `config.py:list_projects()` discovers projects by listing directories. `load_project_config(name)` loads the three YAML files for a project. Falls back to `config/` root if no `projects/` directory exists.

## Data Storage

All runtime data in `data/` (gitignored, Docker volume mount):

```
data/
├── signals/         # Daily signal JSON files (dedup source)
├── approvals/       # Daily approval decision records
├── post_history/    # Audit trail of posted comments
├── campaigns/       # (inherited from OutreachPilot, unused)
├── feedback/        # (inherited from OutreachPilot, unused)
└── scan_history/    # (inherited from OutreachPilot, unused)
```

## Deployment

Docker container on Digital Ocean via Dokploy. Single container runs the scheduler + Telegram bot (`python -m cyrano run`). Config mounted as volume, data persisted as volume.

## CLI Commands

| Command | Mode | What it does |
|---------|------|-------------|
| `python -m cyrano scan` | One-shot | Scan all projects, log actionable signals, exit |
| `python -m cyrano run` | Long-running | Scheduler (cron) + Telegram bot, runs until SIGINT |
| `python -m cyrano bot` | Long-running | Telegram bot only (no scanning), for testing approval flow |
