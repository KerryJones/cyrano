"""Core data models for Cyrano."""

from dataclasses import dataclass, field

from cyrano.analyzers.base import Analysis
from cyrano.scanners.base import RawSignal


@dataclass
class ScoredSignal:
    """A scanned signal combined with its AI analysis and approval state."""
    signal: RawSignal
    analysis: Analysis
    project: str
    signal_id: str  # e.g. "reddit_abc123"

    # Approval state — updated by Telegram bot
    approval_status: str = "pending"  # pending | approved | edited | skipped | posted
    edited_text: str | None = None    # user's edited reply (overrides analysis.suggested_reply)
    telegram_message_id: int | None = None
    approved_at: float | None = None
    posted_at: float | None = None
    comment_url: str | None = None    # URL of posted Reddit comment

    @property
    def reply_text(self) -> str:
        """The text to post: edited if available, otherwise the AI suggestion."""
        if self.edited_text:
            return self.edited_text
        return self.analysis.suggested_reply or self.analysis.suggested_post_comment or ""

    @property
    def is_actionable(self) -> bool:
        """True if this signal is worth sending to Telegram for review."""
        return self.analysis.engage in ("Yes", "Maybe")
