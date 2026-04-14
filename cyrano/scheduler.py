"""APScheduler-based cron runner for Cyrano.

Fires scan cycles on a configurable cron schedule and sends
actionable signals to the Telegram bot for approval.
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cyrano.config import SCAN_CRON, TIMEZONE, list_projects
from cyrano.pipeline import run_scan

logger = logging.getLogger(__name__)


class CyranoScheduler:
    """Wraps APScheduler with Cyrano-specific scan + notify logic."""

    def __init__(self, bot):
        """
        Args:
            bot: CyranoBot instance (must be built before scheduler starts).
        """
        self._bot = bot
        self._scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        self._scheduler.add_job(
            self._scan_and_notify,
            CronTrigger.from_crontab(SCAN_CRON, timezone=TIMEZONE),
            id="cyrano_scan",
            replace_existing=True,
            misfire_grace_time=300,  # allow up to 5 min late start
        )

    def start(self):
        self._scheduler.start()
        logger.info("Scheduler started — cron: '%s' (%s)", SCAN_CRON, TIMEZONE)

    def shutdown(self):
        self._scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    async def _scan_and_notify(self):
        """Run a full scan cycle and send actionable signals to Telegram."""
        projects = list_projects()
        logger.info("Scheduled scan starting — %d project(s)", len(projects))

        for project in projects:
            try:
                scored_signals = await asyncio.get_running_loop().run_in_executor(
                    None, run_scan, project
                )
                actionable = [s for s in scored_signals if s.is_actionable]
                logger.info("[%s] %d actionable signals", project, len(actionable))

                for scored in actionable:
                    await self._bot.send_candidate(scored)

            except Exception as e:
                logger.error("[%s] Scan failed: %s", project, e, exc_info=True)

        logger.info("Scheduled scan complete")
