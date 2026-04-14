"""Cyrano CLI entry point.

Usage:
    python -m cyrano scan              # one-shot scan → Telegram candidates + CSV
    python -m cyrano run               # scheduler + Telegram bot (production)
    python -m cyrano bot               # Telegram bot only (test approval flow)
"""

import argparse
import logging
import sys

logger = logging.getLogger("cyrano")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_scan(args):
    """Run a one-shot scan and send candidates to Telegram."""
    # Phase 1: pipeline refactor will extract this into cyrano/pipeline.py
    import datetime
    import time
    from cyrano.config import (
        get_max_post_age_hours, ensure_data_dirs, list_projects, load_project_config,
    )
    from cyrano.scanners.reddit import RedditScanner
    from cyrano.filters.rule_filter import apply_pre_filters
    from cyrano.analyzers.pipeline import analyze_signal
    from cyrano.exporters.csv_exporter import CSVExporter
    from cyrano.storage.progress import load_progress, save_progress
    from cyrano.storage.signals import save_signals

    ensure_data_dirs()

    projects = list_projects()
    if getattr(args, "project", None):
        projects = [args.project]

    today = datetime.date.today().isoformat()
    scanner = RedditScanner()
    csv_exporter = CSVExporter() if getattr(args, "csv", False) else None

    for project in projects:
        personality, subreddits, filters = load_project_config(project)
        if not subreddits:
            logger.warning("No subreddits configured for project '%s', skipping", project)
            continue

        max_age = get_max_post_age_hours(filters)
        logger.info("[%s] Scanning %d subreddits (last %dh)", project, len(subreddits), max_age)

        progress = load_progress()
        all_signal_dicts = []

        try:
            for i, subreddit in enumerate(subreddits, 1):
                if subreddit in progress["completed_subs"]:
                    continue

                logger.info("  [%d/%d] r/%s", i, len(subreddits), subreddit)
                signals = scanner.scan([subreddit], max_age_hours=max_age)
                raw_count = len(signals)
                signals = apply_pre_filters(signals, filters)

                if not signals:
                    logger.info("    No posts (fetched %d, all filtered)", raw_count)
                else:
                    logger.info("    %d posts (from %d raw)", len(signals), raw_count)
                    for signal in signals:
                        if signal.platform_id in progress["processed_ids"]:
                            continue

                        analysis = analyze_signal(signal, personality=personality, filters=filters)
                        age_hrs = round((time.time() - signal.created_utc) / 3600, 1)

                        signal_dict = {
                            "id": f"reddit_{signal.platform_id}",
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
                            },
                        }
                        all_signal_dicts.append(signal_dict)

                        if analysis.engage in ("Yes", "Maybe"):
                            logger.info(
                                "    → [%s] r/%s: %s",
                                analysis.engage, subreddit, signal.title[:60],
                            )
                        progress["processed_ids"].add(signal.platform_id)

                progress["completed_subs"].add(subreddit)
                save_progress(progress)

        except KeyboardInterrupt:
            logger.info("Interrupted — saving progress...")
        finally:
            if all_signal_dicts:
                save_signals(all_signal_dicts)
            save_progress(progress)
            logger.info("[%s] Done — %d signals processed", project, len(all_signal_dicts))


def cmd_run(args):
    """Start the scheduler and Telegram bot (production mode)."""
    logger.info("Scheduler + Telegram bot not yet implemented (Phase 3/5)")
    logger.info("Run `python -m cyrano scan` for a one-shot scan in the meantime")


def cmd_bot(args):
    """Start the Telegram bot only (for testing the approval flow)."""
    logger.info("Telegram bot not yet implemented (Phase 3)")


def main():
    parser = argparse.ArgumentParser(
        prog="cyrano",
        description="Cyrano — value-first Reddit reply assistant with Telegram approval",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command")

    # scan command
    scan_parser = subparsers.add_parser("scan", help="Run a one-shot scan")
    scan_parser.add_argument("--csv", action="store_true", help="Export results to CSV")
    scan_parser.add_argument("--project", type=str, default=None,
                             help="Scan a specific project only (default: all)")

    # run command
    subparsers.add_parser("run", help="Start scheduler + Telegram bot (production)")

    # bot command
    subparsers.add_parser("bot", help="Start Telegram bot only (test approval flow)")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "bot":
        cmd_bot(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
