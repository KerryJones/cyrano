"""CSV exporter — writes signals to a CSV file."""

import csv
import datetime
import logging
from pathlib import Path

from cyrano.config import DATA_DIR

logger = logging.getLogger(__name__)


class CSVExporter:
    name = "csv"

    def export(self, rows: list[dict], config: dict | None = None) -> Path:
        """Export rows to a CSV file. Returns the file path."""
        filename = (config or {}).get("filename", f"cyrano_{datetime.date.today().isoformat()}.csv")
        filepath = DATA_DIR / filename

        if not rows:
            logger.warning("No rows to export")
            return filepath

        fieldnames = list(rows[0].keys())
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Exported %d rows to %s", len(rows), filepath)
        return filepath
