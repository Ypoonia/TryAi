#!/usr/bin/env python3
"""
Business logic for store monitoring reports.
- One active report at a time (PENDING/RUNNING).
- Idempotent trigger (returns existing active id if present).
- Service returns primitives (not HTTP DTOs).
- No JSON side-car.
"""

import logging
from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.crud import ReportCRUD, RepositoryError
from app.schemas.report import ReportStatus
from app.tasks.report_tasks import generate_report
from app.utils.url_resolver import UrlResolver

logger = logging.getLogger(__name__)

# If you want a single place to tweak the batch size later:
REPORT_MAX_STORES = 50_000


class ReportNotFound(Exception):
    """Raised when a report is not found."""


class ReportService:
    """Business logic for store monitoring reports."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportCRUD
        self.urls = UrlResolver()

    # -------- Public API used by controller --------

    def trigger(self) -> str:
        """
        Idempotent trigger:
          - If an active report (PENDING/RUNNING) exists, return its id (don't enqueue again).
          - Else create PENDING, enqueue worker, set RUNNING, return id.
        """
        try:
            active = self.repo.get_latest_active_report(self.db)
            if active:
                logger.info("Active report exists; idempotent trigger", extra={"report_id": active.report_id})
                return active.report_id

            report_id = self._new_id()
            self.repo.create_report(self.db, report_id, ReportStatus.PENDING)

            # enqueue async work
            logger.info("Enqueueing report generation", extra={"report_id": report_id, "max_stores": REPORT_MAX_STORES})
            generate_report.delay(report_id, REPORT_MAX_STORES)

            # move to RUNNING
            self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.RUNNING)
            return report_id

        except RepositoryError:
            logger.exception("Repository error during trigger")
            raise
        except Exception:
            logger.exception("Unexpected error during trigger")
            raise

    def get_status_with_public_url(self, report_id: str) -> Tuple[str, Optional[str]]:
        """
        Return display status ('Running'|'Complete'|'Failed') and public URL (when complete).
        """
        try:
            rpt = self.repo.get_report_by_id(self.db, report_id)
            if not rpt:
                raise ReportNotFound(report_id)

            status = rpt.status  # string in DB
            if status in (ReportStatus.PENDING.value, ReportStatus.RUNNING.value):
                return "Running", None
            if status == ReportStatus.FAILED.value:
                return "Failed", None

            # COMPLETE
            return "Complete", self.urls.to_public(rpt.url)

        except RepositoryError:
            logger.exception("Repository error during get_status")
            raise
        except Exception:
            logger.exception("Unexpected error during get_status")
            raise

    # -------- Methods for worker to call --------

    def mark_completed(self, report_id: str, internal_url: str) -> None:
        self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.COMPLETE, internal_url)
        logger.info("Report marked COMPLETE", extra={"report_id": report_id})

    def mark_failed(self, report_id: str) -> None:
        self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.FAILED)
        logger.info("Report marked FAILED", extra={"report_id": report_id})

    # -------- helpers --------

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())
