"""Cyrano CLI entry point.

Usage:
    python -m cyrano scan              # one-shot scan → Telegram candidates
    python -m cyrano scan --csv        # also export to CSV
    python -m cyrano scan --project X  # scan one project only
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
    """Run a one-shot scan using the pipeline module."""
    from cyrano.config import ensure_data_dirs, list_projects
    from cyrano.pipeline import run_scan

    ensure_data_dirs()

    projects = list_projects()
    if args.project:
        if args.project not in projects:
            logger.error("Project '%s' not found. Available: %s", args.project, projects)
            sys.exit(1)
        projects = [args.project]

    total_actionable = 0
    for project in projects:
        scored = run_scan(project)
        actionable = [s for s in scored if s.is_actionable]
        total_actionable += len(actionable)

        if actionable:
            logger.info(
                "[%s] %d actionable signals (Telegram approval coming in Phase 3):",
                project, len(actionable),
            )
            for s in actionable:
                logger.info(
                    "  [%s] r/%s — %s",
                    s.analysis.engage,
                    s.signal.metadata.get("subreddit", "?"),
                    s.signal.title[:80],
                )

    logger.info("Scan complete — %d total actionable signals across %d projects",
                total_actionable, len(projects))


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

    scan_parser = subparsers.add_parser("scan", help="Run a one-shot scan")
    scan_parser.add_argument("--csv", action="store_true", help="Export results to CSV")
    scan_parser.add_argument("--project", type=str, default=None,
                             help="Scan a specific project only (default: all)")

    subparsers.add_parser("run", help="Start scheduler + Telegram bot (production)")
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
