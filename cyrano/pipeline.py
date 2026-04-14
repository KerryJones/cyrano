"""Core scan pipeline for Cyrano.

run_scan(project) is the main entry point: loads config for a project,
scans subreddits, pre-filters, deduplicates, runs two-pass LLM analysis,
and returns a list of ScoredSignals ready for Telegram review.
"""

import datetime
import logging
import time

from cyrano.analyzers.pipeline import analyze_signal
from cyrano.config import get_max_post_age_hours, load_project_config
from cyrano.filters.dedup import deduplicate_signals
from cyrano.filters.rule_filter import apply_pre_filters
from cyrano.models import ScoredSignal
from cyrano.scanners.reddit import RedditScanner
from cyrano.storage.progress import load_progress, save_progress
from cyrano.storage.signals import save_signals

logger = logging.getLogger(__name__)

_scanner = RedditScanner()


def run_scan(project: str) -> list[ScoredSignal]:
    """Scan Reddit for a single project and return scored signals.

    Returns all signals that were analyzed. Callers should filter by
    `signal.is_actionable` to get only Yes/Maybe candidates.
    """
    personality, subreddits, filters = load_project_config(project)

    if not subreddits:
        logger.warning("[%s] No subreddits configured — skipping", project)
        return []

    max_age = get_max_post_age_hours(filters)
    logger.info("[%s] Scanning %d subreddits (last %dh)", project, len(subreddits), max_age)

    progress = load_progress()
    scored: list[ScoredSignal] = []
    signal_dicts: list[dict] = []

    try:
        for i, subreddit in enumerate(subreddits, 1):
            if subreddit in progress["completed_subs"]:
                logger.debug("[%s] r/%s already done today — skipping", project, subreddit)
                continue

            logger.info("[%s] [%d/%d] r/%s", project, i, len(subreddits), subreddit)
            signals = _scanner.scan([subreddit], max_age_hours=max_age)
            raw_count = len(signals)
            signals = apply_pre_filters(signals, filters)
            signals = deduplicate_signals(signals)

            if not signals:
                logger.info("  No posts (fetched %d, all pre-filtered)", raw_count)
            else:
                logger.info("  %d posts pass pre-filter (from %d raw)", len(signals), raw_count)

                for signal in signals:
                    if signal.platform_id in progress["processed_ids"]:
                        continue

                    analysis = analyze_signal(signal, personality=personality, filters=filters)
                    age_hrs = round((time.time() - signal.created_utc) / 3600, 1)
                    signal_id = f"reddit_{signal.platform_id}"

                    scored_signal = ScoredSignal(
                        signal=signal,
                        analysis=analysis,
                        project=project,
                        signal_id=signal_id,
                    )
                    scored.append(scored_signal)

                    if analysis.engage in ("Yes", "Maybe"):
                        logger.info(
                            "  → [%s] r/%s: %s",
                            analysis.engage, subreddit, signal.title[:70],
                        )

                    signal_dicts.append({
                        "id": signal_id,
                        "project": project,
                        "platform": "reddit",
                        "platform_id": signal.platform_id,
                        "url": signal.url,
                        "title": signal.title,
                        "body": signal.body[:500],
                        "author": signal.author,
                        "subreddit": subreddit,
                        "score": signal.score,
                        "reply_count": signal.reply_count,
                        "created_utc": signal.created_utc,
                        "age_hrs": age_hrs,
                        "status": signal.status,
                        "analysis": {
                            "summary": analysis.summary,
                            "engage": analysis.engage,
                            "why": analysis.why,
                            "coolest_comment": analysis.coolest_comment,
                            "suggested_reply": analysis.suggested_reply,
                            "suggested_comment": analysis.suggested_post_comment,
                            "model_used": analysis.model_used,
                        },
                    })
                    progress["processed_ids"].add(signal.platform_id)

            progress["completed_subs"].add(subreddit)
            save_progress(progress)

    except KeyboardInterrupt:
        logger.info("[%s] Interrupted — saving progress", project)
    finally:
        if signal_dicts:
            save_signals(signal_dicts)
        save_progress(progress)
        logger.info(
            "[%s] Done — %d signals, %d actionable",
            project, len(scored), sum(1 for s in scored if s.is_actionable),
        )

    return scored
