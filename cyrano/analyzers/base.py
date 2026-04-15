"""Base data models for AI analysis."""

from dataclasses import dataclass


def _clean(value: str) -> str:
    """Normalize LLM output — strip whitespace and placeholder characters."""
    if not value:
        return ""
    value = value.strip()
    if value in ("\u2014", "—", "-", "n/a", "N/A", "none", "None"):
        return ""
    return value


@dataclass
class Analysis:
    """Result of AI analysis on a signal."""
    summary: str
    coolest_comment: str
    suggested_reply: str
    suggested_post_comment: str
    engage: str  # "Yes", "No", "Maybe"
    why: str
    model_used: str = ""
    tokens_used: int = 0

    def __post_init__(self):
        self.summary = _clean(self.summary)
        self.coolest_comment = _clean(self.coolest_comment)
        self.suggested_reply = _clean(self.suggested_reply)
        self.suggested_post_comment = _clean(self.suggested_post_comment)
        self.why = _clean(self.why)

    @staticmethod
    def error_fallback() -> "Analysis":
        return Analysis(
            summary="ERROR: could not analyze",
            coolest_comment="",
            suggested_reply="",
            suggested_post_comment="",
            engage="No",
            why="Analysis failed",
        )
