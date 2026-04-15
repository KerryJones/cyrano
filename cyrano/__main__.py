"""Cyrano CLI entry point.

Usage:
    python -m cyrano scan              # one-shot scan → log actionable signals
    python -m cyrano scan --project X  # scan one project only
    python -m cyrano run               # scheduler + Telegram bot (production)
    python -m cyrano bot               # Telegram bot only (test approval flow)
"""

import argparse
import asyncio
import logging
import signal
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
    """Run a one-shot scan and send actionable signals to Telegram."""
    from cyrano.config import ensure_data_dirs, list_projects
    from cyrano.pipeline import run_scan

    ensure_data_dirs()

    projects = list_projects()
    if args.project:
        if args.project not in projects:
            logger.error("Project '%s' not found. Available: %s", args.project, projects)
            sys.exit(1)
        projects = [args.project]

    all_actionable = []
    for project in projects:
        scored = run_scan(project)
        actionable = [s for s in scored if s.is_actionable]
        all_actionable.extend(actionable)
        for s in actionable:
            logger.info(
                "  [%s] r/%s — %s",
                s.analysis.engage,
                s.signal.metadata.get("subreddit", "?"),
                s.signal.title[:80],
            )

    logger.info(
        "Scan complete — %d actionable across %d project(s)",
        len(all_actionable), len(projects),
    )

    if all_actionable:
        asyncio.run(_send_candidates(all_actionable))


async def _send_candidates(actionable):
    """Send actionable signals to Telegram for review."""
    from cyrano.telegram.bot import CyranoBot

    bot = CyranoBot()
    await bot.build()
    await bot.start()

    for scored in actionable:
        await bot.send_candidate(scored)
        logger.info("Sent to Telegram: %s", scored.signal_id)

    await bot.stop()


async def _run_async():
    """Start the scheduler + Telegram bot and run until SIGINT/SIGTERM."""
    from cyrano.config import ensure_data_dirs
    from cyrano.telegram.bot import CyranoBot
    from cyrano.scheduler import CyranoScheduler

    ensure_data_dirs()

    bot = CyranoBot()
    await bot.build()

    scheduler = CyranoScheduler(bot)

    logger.info("Starting Cyrano — scheduler + Telegram bot")
    await bot.start()
    scheduler.start()

    # Block until SIGINT/SIGTERM
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    logger.info("Shutdown signal received")
    scheduler.shutdown()
    await bot.stop()


def cmd_run(args):
    """Start scheduler + Telegram bot (production mode)."""
    asyncio.run(_run_async())


async def _bot_only_async():
    """Run just the Telegram bot for testing the approval flow."""
    from cyrano.config import ensure_data_dirs
    from cyrano.telegram.bot import CyranoBot

    ensure_data_dirs()
    bot = CyranoBot()
    await bot.build()
    logger.info("Bot-only mode — waiting for Telegram callbacks")
    await bot.start()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await stop_event.wait()
    await bot.stop()


def cmd_bot(args):
    """Start Telegram bot only (test approval flow without scanning)."""
    asyncio.run(_bot_only_async())


def cmd_send(args):
    """Re-send today's (or a specific date's) actionable signals to Telegram."""
    from cyrano.storage.signals import load_signals
    from cyrano.analyzers.base import Analysis
    from cyrano.scanners.base import RawSignal
    from cyrano.models import ScoredSignal

    date_str = args.date or datetime.date.today().isoformat()
    signals = load_signals(date_str)

    if not signals:
        logger.info("No signals found for %s", date_str)
        return

    actionable = []
    for s in signals:
        a = s.get("analysis", {})
        if a.get("engage") not in ("Yes", "Maybe"):
            continue

        sig = RawSignal(
            platform=s["platform"],
            platform_id=s["platform_id"],
            url=s["url"],
            title=s["title"],
            body=s.get("body", ""),
            author=s.get("author", ""),
            score=s.get("score", 0),
            reply_count=s.get("reply_count", 0),
            created_utc=s.get("created_utc", 0),
            metadata={"subreddit": s.get("subreddit", "")},
        )
        analysis = Analysis(
            summary=a.get("summary", ""),
            coolest_comment=a.get("coolest_comment", ""),
            suggested_reply=a.get("suggested_reply", ""),
            suggested_post_comment=a.get("suggested_comment", ""),
            engage=a["engage"],
            why=a.get("why", ""),
            model_used=a.get("model_used", ""),
        )
        scored = ScoredSignal(
            signal=sig, analysis=analysis,
            project=s.get("project", ""), signal_id=s["id"],
        )
        actionable.append(scored)

    if not actionable:
        logger.info("No actionable signals for %s", date_str)
        return

    logger.info("Sending %d actionable signals from %s to Telegram", len(actionable), date_str)
    asyncio.run(_send_candidates(actionable))


def main():
    import datetime

    parser = argparse.ArgumentParser(
        prog="cyrano",
        description="Cyrano — value-first Reddit reply assistant with Telegram approval",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Run a one-shot scan")
    scan_parser.add_argument("--project", type=str, default=None,
                             help="Scan a specific project only (default: all)")

    send_parser = subparsers.add_parser("send", help="Re-send actionable signals to Telegram")
    send_parser.add_argument("--date", type=str, default=None,
                             help="Date to send (YYYY-MM-DD, default: today)")

    subparsers.add_parser("run", help="Start scheduler + Telegram bot (production)")
    subparsers.add_parser("bot", help="Start Telegram bot only (test approval flow)")

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "send":
        cmd_send(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "bot":
        cmd_bot(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
