# Cyrano

Value-first Reddit reply assistant with Telegram approval flow.

Scans Reddit communities for relevant conversations, drafts helpful replies via AI, and sends candidates to Telegram for human approval before posting. Named after [Cyrano de Bergerac](https://en.wikipedia.org/wiki/Cyrano_de_Bergerac_(play)) — the original reply guy.

Forked from [OutreachPilot](https://github.com/sausi-7/reddit-outreach), rewritten with Claude, Telegram, and PRAW.

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## How It Works

```
config/projects/{name}/
  personality.yml       Your voice, tone, project info
  subreddits.yml        Communities to monitor
  filters.yml           Pre-filters + AI scoring preferences
        |
        v
  ┌─────────────────────────────┐
  │  Reddit scanner             │  Public JSON API, rate-limited
  └─────────────────────────────┘
        |
        v
  ┌─────────────────────────────┐
  │  Pre-filter (zero AI cost)  │  Keywords, score, age, flairs
  └─────────────────────────────┘
        |
        v
  ┌─────────────────────────────┐
  │  Pass 1: Haiku scoring      │  Yes / Maybe / No + why
  └─────────────────────────────┘
        |  (only Yes/Maybe continue)
        v
  ┌─────────────────────────────┐
  │  Pass 2: Sonnet drafting    │  Full reply in your voice
  └─────────────────────────────┘
        |
        v
  ┌─────────────────────────────┐
  │  Telegram approval card     │  [Approve] [Edit] [Skip] [No Plug]
  └─────────────────────────────┘
        |
        v
  ┌─────────────────────────────┐
  │  Post via PRAW              │  From your Reddit account
  └─────────────────────────────┘
```

Every reply is human-approved. The AI drafts; you decide.

---

## Quick Start

```bash
git clone https://github.com/KerryJones/cyrano.git
cd cyrano
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy and fill in your credentials:

```bash
cp .env.example .env
```

Required in `.env`:
- `ANTHROPIC_API_KEY` — for Claude via LiteLLM
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — your personal chat ID
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD` — for posting

---

## Commands

```bash
python -m cyrano scan              # One-shot scan, log actionable signals
python -m cyrano scan --project X  # Scan one project only
python -m cyrano run               # Scheduler + Telegram bot (production)
python -m cyrano bot               # Telegram bot only (test approval flow)
```

---

## Multi-Project Config

Each project gets its own directory under `config/projects/`:

```
config/projects/
├── matcha/
│   ├── personality.yml    # Voice, bio, project info, plug criteria
│   ├── subreddits.yml     # Communities to monitor
│   └── filters.yml        # Pre-filters + AI preferences
├── rowcraft/
│   └── ...
└── dealcred/
    └── ...
```

Cyrano scans all projects on each cycle. Telegram cards are tagged with the project name.

### personality.yml

Defines your voice and when to mention your project:

```yaml
name: "Kerry"
bio: "Software engineer who rows on a Concept2 daily..."

project:
  name: "RowCraft"
  description: "Structured Concept2 workouts with BLE coaching"
  plug_when:
    - someone is asking for a Concept2 workout app

tone:
  style: "fellow rower who's also an engineer"

dos:
  - Share specific workout recommendations with splits
donts:
  - Never lead with the app — always lead with advice

example_comments:
  - "For a 2K, your target should be roughly your steady state pace minus 6-8 splits..."
```

### filters.yml

Pre-filters run before any AI calls (zero cost). AI preferences guide the Yes/Maybe/No scoring:

```yaml
thresholds:
  min_score: 2
  max_comments: 300
  max_age_hours: 24

ai_preferences:
  prefer_topics:
    - asking for help or recommendations
  avoid_topics:
    - memes with no substance
  engagement_notes: >
    Value-first. Only mention the project if it directly solves their problem.
```

---

## Two-Pass LLM Strategy

Cost optimization: most signals are "No" and never hit the expensive model.

| Pass | Model | Purpose | Cost |
|------|-------|---------|------|
| 1 | Haiku | Relevance scoring (Yes/Maybe/No + why) | ~$0.001/signal |
| 2 | Sonnet | Full reply drafting (only for Yes/Maybe) | ~$0.01/signal |

For 2-3 projects with ~15 subreddits, 2 scans/day: **~$4-5/month**.

---

## Scheduler

Runs scans automatically during configured hours:

```env
SCAN_CRON=*/30 8-20 * * *    # Every 30 min, 8am-8pm
TIMEZONE=America/New_York
```

---

## Deployment

Docker + Dokploy (or any Docker host):

```bash
docker compose up --build -d
```

```yaml
# docker-compose.yml
services:
  cyrano:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    restart: unless-stopped
```

---

## Project Structure

```
cyrano/
├── cyrano/
│   ├── __main__.py          # CLI: scan / run / bot
│   ├── pipeline.py          # Scan orchestration
│   ├── models.py            # ScoredSignal dataclass
│   ├── config.py            # Settings + multi-project loading
│   ├── scheduler.py         # APScheduler cron runner
│   ├── scanners/
│   │   ├── base.py          # Scanner protocol + data models
│   │   └── reddit.py        # Reddit JSON API scanner
│   ├── analyzers/
│   │   ├── pipeline.py      # Two-pass analysis (Haiku + Sonnet)
│   │   ├── llm_client.py    # LiteLLM wrapper
│   │   └── base.py          # Analysis dataclass
│   ├── telegram/
│   │   ├── bot.py           # Approval flow + callback handlers
│   │   └── formatter.py     # Message rendering + keyboards
│   ├── reddit/
│   │   └── poster.py        # PRAW posting with rate limiting
│   ├── filters/
│   │   ├── rule_filter.py   # Pre-filter (keywords, score, age)
│   │   └── dedup.py         # Cross-day deduplication
│   ├── personas/
│   │   └── prompt_builder.py # LLM prompt construction
│   └── storage/
│       ├── signals.py       # Daily signal JSON files
│       ├── approvals.py     # Approval decision records
│       ├── post_history.py  # Posted reply audit trail
│       └── progress.py      # Checkpoint/resume
├── config/
│   └── projects/            # Per-project YAML configs
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## License

[AGPL-3.0](LICENSE) — Free to use, modify, and self-host.

Forked from [OutreachPilot](https://github.com/sausi-7/reddit-outreach) by [Saurabh Singh](https://github.com/sausi-7).
