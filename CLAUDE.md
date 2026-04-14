# Cyrano

Value-first Reddit reply assistant. Scans communities for relevant conversations, drafts helpful replies via AI (two-pass: Haiku scoring, Sonnet drafting), sends candidates to Telegram for human approval, posts via PRAW.

Stack: Python 3.14, LiteLLM (Claude), python-telegram-bot v21, PRAW, APScheduler, Docker, Dokploy (Digital Ocean).

## Rules

### Ownership & Quality
- You own this codebase. A failing test is always your bug.
- Write tests alongside features — happy path, error paths, edge cases.
- Run `ruff check cyrano/` and `pytest` before presenting work as done.
- Resolve TODOs in files you touch if they're in scope.

### Coding Principles
**CONSISTENT > CANONICAL > SIMPLE**
1. Match existing patterns in the codebase first
2. Use the standard/documented approach for the library/framework
3. Prefer the simplest solution that works

### Code Style
- Python 3.14, type hints everywhere, dataclasses for models
- `async` where Telegram/APScheduler requires it, sync elsewhere
- Logging via stdlib `logging`, never `print()`
- No backward-compat shims — this has never shipped
- MarkdownV2 in Telegram: always escape with `_esc()`, use `"\u2014"` for em-dash

### Research Before Guessing
- Never fabricate or guess API behavior, Reddit rules, or Telegram bot API details. Use WebSearch/WebFetch.

### Communication
- No sycophancy. State what you think directly.
- Push back when appropriate.

### Tool Usage
- Prefer Claude Code tools (Read, Edit, Write, Glob, Grep) over Bash equivalents.
- No compound Bash commands (pipes, `cd &&`, chained commands).
- No git commits without explicit user permission.
- Allowlisted Bash: `make`, `git`, `ruff`, `pytest`.

### Memory Discipline
- Do not save architecture, file paths, or code patterns to MEMORY.md.
- MEMORY.md is only for user preferences and feedback.
- Reference docs belong in `docs/` if they need to be persisted.
- Keep CLAUDE.md under 100 lines.

## Commands

```
make setup    # create venv + install deps
make scan     # one-shot scan
make run      # scheduler + Telegram bot (production)
make bot      # Telegram bot only (test approval flow)
```

## Reference Docs

| File | Contents |
|------|----------|
| `docs/architecture.md` | Pipeline, data flow, module map, deployment |
