import logging
from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.crud import ReportCRUD, RepositoryError
from app.schemas.report import ReportStatus
from app.tasks.report_tasks import generate_report
from app.utils.url_resolver import UrlResolver

logger = logging.getLogger(__name__)

REPORT_MAX_STORES = 50_000


class ReportNotFound(Exception):
    pass


class ReportService:

    def __init__(self, db: Session):
        self.db = db
        self.repo = ReportCRUD
        self.urls = UrlResolver()

    def trigger(self) -> str:
        try:
            active = self.repo.get_latest_active_report(self.db)
            if active:
                logger.info("Active report exists; idempotent trigger", extra={"report_id": active.report_id})
                return active.report_id

            report_id = self._new_id()
            self.repo.create_report(self.db, report_id, ReportStatus.PENDING)

            logger.info("Enqueueing report generation", extra={"report_id": report_id, "max_stores": REPORT_MAX_STORES})
            generate_report.delay(report_id, REPORT_MAX_STORES)

            self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.RUNNING)
            return report_id

        except RepositoryError:
            logger.exception("Repository error during trigger")
            raise
        except Exception:
            logger.exception("Unexpected error during trigger")
            raise

    def get_status_with_public_url(self, report_id: str) -> Tuple[str, Optional[str]]:
        try:
            rpt = self.repo.get_report_by_id(self.db, report_id)
            if not rpt:
                raise ReportNotFound(report_id)

            status = rpt.status
            if status in (ReportStatus.PENDING.value, ReportStatus.RUNNING.value):
                return "Running", None
            if status == ReportStatus.FAILED.value:
                return "Failed", None

            return "Complete", self.urls.to_public(rpt.url)

        except RepositoryError:
            logger.exception("Repository error during get_status")
            raise
        except Exception:
            logger.exception("Unexpected error during get_status")
            raise

    def mark_completed(self, report_id: str, internal_url: str) -> None:
        self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.COMPLETE, internal_url)
        logger.info("Report marked COMPLETE", extra={"report_id": report_id})

    def mark_failed(self, report_id: str) -> None:
        self.repo.set_report_status_and_url(self.db, report_id, ReportStatus.FAILED)
        logger.info("Report marked FAILED", extra={"report_id": report_id})

    @staticmethod
    def _new_id() -> str:
        return str(uuid4())
