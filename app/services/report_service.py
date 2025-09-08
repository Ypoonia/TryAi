#!/usr/bin/env python3
"""
Business logic for store monitoring reports.
- Idempotent: one active report at a time.
- Proper error handling via exceptions.
- Clear separation between domain logic and persistence.
"""

import os
import logging
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.crud import ReportCRUD, RepositoryError
from app.schemas.report import ReportStatus, ReportResponse, ReportStatusResponse
from app.tasks.report_tasks import generate_report
from app.utils.url_resolver import UrlResolver

logger = logging.getLogger(__name__)


class ReportServiceError(Exception):
    """Raised on service layer business logic errors"""
    pass


class ReportService:
    """Business logic for store monitoring reports"""

    @staticmethod
    def trigger_report(db: Session) -> ReportResponse:
        """
        Start a new report generation if no active report exists.
        Returns the new report ID or the existing active report.
        Idempotent: only one active report at a time.
        """
        try:
            # Check for existing active report
            active_report = ReportCRUD.get_latest_active_report(db)
            if active_report:
                logger.info(
                    "Active report already exists",
                    extra={"report_id": active_report.report_id, "status": active_report.status},
                )
                return ReportResponse(
                    report_id=active_report.report_id,
                    status=ReportStatus(active_report.status),
                    message="Report generation already in progress",
                )

            # Generate new report ID and create pending record
            report_id = str(uuid4())
            new_report = ReportCRUD.create_report(db, report_id, ReportStatus.PENDING)

            # Start background task
            generate_report.delay(report_id, 50000)

            logger.info("New report triggered", extra={"report_id": report_id})
            return ReportResponse(
                report_id=report_id,
                status=ReportStatus.PENDING,
                message="Report generation started",
            )

        except RepositoryError as e:
            logger.exception("Repository error during report trigger")
            raise ReportServiceError(f"Database error: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error during report trigger")
            raise ReportServiceError(f"Failed to trigger report: {e}") from e

    @staticmethod
    def get_report_status(db: Session, report_id: str) -> ReportStatusResponse:
        """
        Get the status of a specific report.
        Transform file:// URLs to public URLs for external consumption.
        """
        try:
            report = ReportCRUD.get_report_by_id(db, report_id)
            if not report:
                logger.warning("Report not found", extra={"report_id": report_id})
                raise ReportServiceError(f"Report {report_id} not found")

            status = ReportStatus(report.status)
            public_url = None

            # Transform file URLs to public URLs for completed reports
            if status == ReportStatus.COMPLETED and report.url:
                public_url = UrlResolver.to_public(report.url)

            logger.debug(
                "Report status retrieved",
                extra={
                    "report_id": report_id,
                    "status": status.value,
                    "has_url": public_url is not None,
                },
            )

            return ReportStatusResponse(
                report_id=report_id,
                status=status,
                url=public_url,
            )

        except RepositoryError as e:
            logger.exception("Repository error during status check")
            raise ReportServiceError(f"Database error: {e}") from e
        except ValueError as e:
            # Invalid enum value from database
            logger.error("Invalid status in database", extra={"report_id": report_id, "status": report.status})
            raise ReportServiceError(f"Invalid report status: {e}") from e
        except Exception as e:
            logger.exception("Unexpected error during status check")
            raise ReportServiceError(f"Failed to get report status: {e}") from e

    @staticmethod
    def mark_report_running(db: Session, report_id: str) -> None:
        """Mark a report as RUNNING (called by background task)"""
        try:
            ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.RUNNING)
            logger.info("Report marked as running", extra={"report_id": report_id})
        except RepositoryError as e:
            logger.exception("Repository error marking report as running")
            raise ReportServiceError(f"Database error: {e}") from e

    @staticmethod
    def mark_report_completed(db: Session, report_id: str, file_url: str) -> None:
        """Mark a report as COMPLETED with file URL (called by background task)"""
        try:
            ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.COMPLETED, file_url)
            logger.info(
                "Report marked as completed",
                extra={"report_id": report_id, "file_url": file_url},
            )
        except RepositoryError as e:
            logger.exception("Repository error marking report as completed")
            raise ReportServiceError(f"Database error: {e}") from e

    @staticmethod
    def mark_report_failed(db: Session, report_id: str, error_msg: Optional[str] = None) -> None:
        """Mark a report as FAILED (called by background task)"""
        try:
            ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.FAILED)
            logger.error(
                "Report marked as failed",
                extra={"report_id": report_id, "error": error_msg},
            )
        except RepositoryError as e:
            logger.exception("Repository error marking report as failed")
            raise ReportServiceError(f"Database error: {e}") from e

    @staticmethod
    def get_report_file_path(report_id: str, format_type: str = "csv") -> str:
        """Generate file path for report output"""
        reports_dir = os.path.join(os.getcwd(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        return os.path.join(reports_dir, f"{report_id}.{format_type}")
