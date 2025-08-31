#!/usr/bin/env python3
"""
CRUD operations for Store Monitoring System
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc, text
from app.models.report import Report
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ReportCRUD:
    """CRUD operations for Report model"""
    
    @staticmethod
    def create_report(db: Session, report_id: str, status: str = "PENDING") -> Report:
        """Create a new report"""
        try:
            db_report = Report(
                report_id=report_id,
                status=status
            )
            db.add(db_report)
            db.commit()
            db.refresh(db_report)
            logger.info(f"Report {report_id} created successfully")
            return db_report
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating report {report_id}: {e}")
            raise
    
    @staticmethod
    def get_report_by_id(db: Session, report_id: str) -> Optional[Report]:
        """Get report by ID"""
        try:
            return db.query(Report).filter(Report.report_id == report_id).first()
        except Exception as e:
            logger.error(f"Error getting report {report_id}: {e}")
            return None
    
    @staticmethod
    def get_latest_pending_report(db: Session) -> Optional[Report]:
        """Get the most recent PENDING or RUNNING report"""
        try:
            return db.query(Report).filter(
                Report.status.in_(["PENDING", "RUNNING"])
            ).order_by(desc(Report.created_at)).first()
        except Exception as e:
            logger.error(f"Error getting latest pending/running report: {e}")
            return None
    
    @staticmethod
    def update_report_status(db: Session, report_id: str, new_status: str) -> Optional[Report]:
        """Update report status"""
        try:
            db_report = db.query(Report).filter(Report.report_id == report_id).first()
            if db_report:
                db_report.status = new_status
                db.commit()
                db.refresh(db_report)
                logger.info(f"Report {report_id} status updated to {new_status}")
                return db_report
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating report {report_id} status: {e}")
            return None
    
    @staticmethod
    def set_report_status_and_url(db: Session, report_id: str, status: str, url: Optional[str] = None) -> Optional[Report]:
        """Update report status and URL (business logic helper)"""
        try:
            db_report = db.query(Report).filter(Report.report_id == report_id).first()
            if db_report:
                db_report.status = status
                if url is not None:
                    db_report.url = url
                db.commit()
                db.refresh(db_report)
                logger.info(f"Report {report_id} updated: status={status}, url={url}")
                return db_report
            return None
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating report {report_id} status and URL: {e}")
            return None
    
    @staticmethod
    def get_all_reports(db: Session, skip: int = 0, limit: int = 100) -> List[Report]:
        """Get all reports with pagination"""
        try:
            return db.query(Report).offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting all reports: {e}")
            return []
    
    @staticmethod
    def delete_report(db: Session, report_id: str) -> bool:
        """Delete a report"""
        try:
            db_report = db.query(Report).filter(Report.report_id == report_id).first()
            if db_report:
                db.delete(db_report)
                db.commit()
                logger.info(f"Report {report_id} deleted successfully")
                return True
            return False
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting report {report_id}: {e}")
            return False


def check_database_health(db: Session) -> Dict[str, Any]:
    """Check database connectivity and health"""
    try:
        # Try to execute a simple query
        result = db.execute(text("SELECT 1")).scalar()
        
        if result == 1:
            return {"ok": True, "database": "connected"}
        else:
            return {"ok": False, "database": "query_failed"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"ok": False, "database": str(e)}
