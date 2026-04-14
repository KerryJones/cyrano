"""Formats ScoredSignal into a Telegram message + inline keyboard."""

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from cyrano.models import ScoredSignal


def format_candidate(scored: ScoredSignal) -> tuple[str, InlineKeyboardMarkup]:
    """Build the message text and keyboard for a Telegram approval card.

    Returns:
        (message_text, keyboard)
    """
    s = scored.signal
    a = scored.analysis
    subreddit = s.metadata.get("subreddit", s.platform)
    age_hrs = round((time.time() - s.created_utc) / 3600, 1)

    engage_icon = "✅" if a.engage == "Yes" else "🤔"

    lines = [
        f"*\\[{_esc(scored.project)}\\] r/{_esc(subreddit)}* {engage_icon}",
        f"📝 {_esc(s.title)}",
        f"Score: {s.score} \\| Comments: {s.reply_count} \\| Age: {age_hrs}h",
        f"🔗 {s.url}",
        "",
        f"*Summary:* {_esc(a.summary)}",
        f"*Why:* {_esc(a.why)}",
    ]

    if a.coolest_comment and a.coolest_comment != "no cool comments":
        lines += [
            "",
            f"*Top comment:* _{_esc(a.coolest_comment[:200])}_",
        ]

    reply_text = scored.reply_text
    if reply_text and reply_text != "—":
        lines += [
            "",
            "─────────────────",
            "*Suggested reply:*",
            _esc(reply_text),
        ]

    text = "\n".join(lines)

    sid = scored.signal_id
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{sid}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{sid}"),
        ],
        [
            InlineKeyboardButton("⏭ Skip", callback_data=f"skip:{sid}"),
            InlineKeyboardButton("🚫 No Plug", callback_data=f"noplug:{sid}"),
        ],
    ])

    return text, keyboard


def format_status_update(scored: ScoredSignal, status: str, extra: str = "") -> str:
    """Build a short status line to replace the keyboard after a decision."""
    icons = {
        "approved": "✅ Approved",
        "edited": "✏️ Approved (edited)",
        "skipped": "⏭ Skipped",
        "noplug": "🚫 Approved (no plug)",
        "posted": "📬 Posted",
        "error": "❌ Error",
    }
    label = icons.get(status, status)
    subreddit = scored.signal.metadata.get("subreddit", "?")
    base = f"{label} — r/{subreddit}: {scored.signal.title[:60]}"
    return f"{base}\n{extra}" if extra else base


def _esc(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    if not text:
        return ""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
