#!/usr/bin/env python3
"""
Repository (CRUD) operations for Report model with consistent behavior.
- Returns domain objects on success.
- Returns None only for "not found" lookups.
- Raises on DB failures (so upper layers aren't forced to guess).
"""

from typing import Optional
import logging

from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from sqlalchemy.exc import SQLAlchemyError

from app.models.report import Report
from app.schemas.report import ReportStatus

logger = logging.getLogger(__name__)


class RepositoryError(RuntimeError):
    pass


class ReportCRUD:
    """Repository for Report model"""

    def create_report(db: Session, report_id: str, status: ReportStatus = ReportStatus.PENDING) -> Report:
        try:
            db_report = Report(report_id=report_id, status=status.value)
            db.add(db_report)
            db.commit()
            db.refresh(db_report)
            logger.info("Report created", extra={"report_id": report_id, "status": status.value})
            return db_report
        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("DB error creating report")
            raise RepositoryError(str(e)) from e

    def get_report_by_id(db: Session, report_id: str) -> Optional[Report]:
        try:
            return db.query(Report).filter(Report.report_id == report_id).first()
        except SQLAlchemyError as e:
            logger.exception("DB error fetching report by id")
            raise RepositoryError(str(e)) from e

    def get_latest_active_report(db: Session) -> Optional[Report]:
        """
        Return most recent report with status in (PENDING, RUNNING).
        """
        try:
            return (
                db.query(Report)
                .filter(Report.status.in_([ReportStatus.PENDING.value, ReportStatus.RUNNING.value]))
                .order_by(desc(Report.created_at))
                .first()
            )
        except SQLAlchemyError as e:
            logger.exception("DB error fetching latest active report")
            raise RepositoryError(str(e)) from e

    def set_report_status_and_url(
        db: Session, report_id: str, status: ReportStatus, url: Optional[str] = None
    ) -> Report:
        try:
            db_report = db.query(Report).filter(Report.report_id == report_id).first()
            if not db_report:
                raise RepositoryError(f"Report {report_id} not found")
            db_report.status = status.value
            if url is not None:
                db_report.url = url
            db.commit()
            db.refresh(db_report)
            logger.info(
                "Report updated",
                extra={"report_id": report_id, "status": status.value, "has_url": url is not None},
            )
            return db_report
        except SQLAlchemyError as e:
            db.rollback()
            logger.exception("DB error updating report status/url")
            raise RepositoryError(str(e)) from e

    # Legacy method names for compatibility with existing code
    def get_latest_pending_report(db: Session) -> Optional[Report]:
        """Legacy alias for get_latest_active_report"""
        return ReportCRUD.get_latest_active_report(db)

    def update_report_status(db: Session, report_id: str, new_status: str) -> Optional[Report]:
        """Legacy method - convert string status to enum"""
        try:
            status_enum = ReportStatus(new_status)
            return ReportCRUD.set_report_status_and_url(db, report_id, status_enum)
        except ValueError:
            logger.error(f"Invalid status: {new_status}")
            raise RepositoryError(f"Invalid status: {new_status}")


def check_database_health(db: Session) -> dict:
    """Simple database connectivity check"""
    try:
        # Simple query to test database connectivity
        result = db.execute(text("SELECT 1")).scalar()
        return {
            "ok": result == 1,
            "database": "connected"
        }
    except SQLAlchemyError as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "ok": False,
            "database": f"error: {str(e)}"
        }

