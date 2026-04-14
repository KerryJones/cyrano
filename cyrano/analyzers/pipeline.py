"""Two-pass analysis pipeline.

Pass 1 (Haiku — cheap): score relevance → Yes / Maybe / No + why.
Pass 2 (Sonnet — quality): draft full reply, only for Yes/Maybe signals.

This keeps costs low: only ~10-20% of signals reach the expensive drafting pass.
"""

import logging

from cyrano.analyzers.base import Analysis
from cyrano.analyzers.llm_client import chat_completion
from cyrano.config import LLM_SCORING_MODEL, LLM_DRAFTING_MODEL
from cyrano.personas.prompt_builder import (
    build_personality_block, build_ai_prefs_block, build_scoring_context,
)
from cyrano.scanners.base import RawSignal

logger = logging.getLogger(__name__)


def _build_comments_text(signal: RawSignal) -> str:
    if signal.replies:
        lines = []
        for i, c in enumerate(signal.replies[:10], 1):
            lines.append(f"{i}. [score: {c.score}] u/{c.author}: {c.body}")
        return "\n" + "\n".join(lines)
    return "\n(No comments yet)"


def _score_signal(signal: RawSignal, personality: dict, filters: dict) -> dict | None:
    """Pass 1: cheap relevance scoring with the scoring model (Haiku)."""
    subreddit = signal.metadata.get("subreddit", signal.platform)
    comments_text = _build_comments_text(signal)
    scoring_context = build_scoring_context(personality)
    ai_prefs_block = build_ai_prefs_block(filters)

    prompt = f"""{scoring_context}

You are evaluating whether this Reddit post is worth replying to, given the person's
background, expertise, and interests described above.

Subreddit: r/{subreddit}
Post title: {signal.title}
Post body: {signal.body or '(no body text)'}
Score: {signal.score} | Comments: {signal.reply_count}

Top comments:{comments_text}
{ai_prefs_block}

Would this person have something genuinely valuable to contribute here?
Return JSON (no markdown) with:
- "engage": "Yes", "Maybe", or "No"
- "why": one sentence explaining the decision

Score "Yes" when the post is a clear fit for this person's expertise or interests.
Score "Maybe" when they could add value but it's not a perfect match.
Score "No" when the topic is outside their wheelhouse or the conversation is already saturated."""

    return chat_completion(prompt, model=LLM_SCORING_MODEL)


def _draft_reply(signal: RawSignal, personality: dict, filters: dict) -> dict | None:
    """Pass 2: full reply drafting with the drafting model (Sonnet)."""
    subreddit = signal.metadata.get("subreddit", signal.platform)
    comments_text = _build_comments_text(signal)
    personality_block = build_personality_block(personality)
    ai_prefs_block = build_ai_prefs_block(filters)

    prompt = f"""You are drafting a helpful Reddit reply.

{personality_block}

Subreddit: r/{subreddit}
Post title: {signal.title}
Post body: {signal.body or '(no body text)'}
Score: {signal.score} | Comments: {signal.reply_count}

Top comments:{comments_text}
{ai_prefs_block}

Write a genuinely helpful reply. Only mention your product/project if it is directly relevant
and would help the person — never force it. Match the community's tone.

Return JSON (no markdown) with:
- "summary": 1-2 sentence summary of the post
- "coolest_comment": the most interesting comment verbatim, or "no cool comments"
- "suggested_reply": a reply to that cool comment in your voice; "\u2014" if no cool comment
- "suggested_post_comment": a helpful comment on the post itself, in your voice
- "why": one sentence on why this is worth engaging with"""

    return chat_completion(prompt, model=LLM_DRAFTING_MODEL)


def analyze_signal(
    signal: RawSignal,
    personality: dict | None = None,
    filters: dict | None = None,
) -> Analysis:
    """Analyze a signal with two-pass LLM strategy.

    Pass 1 (cheap): determine if worth engaging.
    Pass 2 (quality): draft reply — only for Yes/Maybe signals.
    """
    personality = personality or {}
    filters = filters or {}

    # Pass 1: scoring
    score_result = _score_signal(signal, personality, filters)
    if score_result is None:
        return Analysis.error_fallback()

    engage = score_result.get("engage", "No")
    why = score_result.get("why", "")

    if engage == "No":
        return Analysis(
            summary="",
            coolest_comment="no cool comments",
            suggested_reply="\u2014",
            suggested_post_comment="\u2014",
            engage="No",
            why=why,
            model_used=LLM_SCORING_MODEL,
        )

    # Pass 2: drafting (only for Yes/Maybe)
    draft_result = _draft_reply(signal, personality, filters)
    if draft_result is None:
        # Scoring passed but drafting failed — return minimal Yes/Maybe with why
        return Analysis(
            summary="",
            coolest_comment="no cool comments",
            suggested_reply="\u2014",
            suggested_post_comment="\u2014",
            engage=engage,
            why=why,
            model_used=LLM_SCORING_MODEL,
        )

    return Analysis(
        summary=draft_result.get("summary", ""),
        coolest_comment=draft_result.get("coolest_comment", "no cool comments"),
        suggested_reply=draft_result.get("suggested_reply", "\u2014"),
        suggested_post_comment=draft_result.get("suggested_post_comment", "\u2014"),
        engage=engage,
        why=draft_result.get("why", why),
        model_used=f"{LLM_SCORING_MODEL}+{LLM_DRAFTING_MODEL}",
    )
