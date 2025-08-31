#!/usr/bin/env python3
"""
Celery tasks for async report generation
"""

import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.services.minute_index_report_service import MinuteIndexReportService
from app.database.crud import ReportCRUD
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.report_tasks.generate_report")
def generate_report(self, report_id: str):
    """
    Celery task to generate store monitoring report asynchronously
    
    Flow:
    1. Mark report as RUNNING
    2. Generate report using MinuteIndexReportService
    3. Mark report as COMPLETE with file path
    """
    
    logger.info(f"Starting async report generation for {report_id}")
    
    try:
        # Create database connection
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Step 1: Mark report as RUNNING
        logger.info(f"Marking report {report_id} as RUNNING")
        ReportCRUD.update_report_status(db, report_id, "RUNNING")
        
        # Step 2: Generate report
        logger.info(f"Generating report {report_id}")
        service = MinuteIndexReportService(db)
        result = service.generate_store_report(report_id, max_stores=100)
        
        if result["success"]:
            # Step 3: Mark report as COMPLETE with file path
            file_path = result["file_path"]
            logger.info(f"Report {report_id} completed successfully: {file_path}")
            ReportCRUD.set_report_status_and_url(db, report_id, "COMPLETE", file_path)
            
            return {
                "success": True,
                "report_id": report_id,
                "file_path": file_path,
                "total_stores": result["total_stores"],
                "completed_at": datetime.utcnow().isoformat()
            }
        else:
            # Mark as FAILED
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Report {report_id} failed: {error_msg}")
            ReportCRUD.update_report_status(db, report_id, "FAILED")
            
            return {
                "success": False,
                "report_id": report_id,
                "error": error_msg,
                "failed_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        # Mark as FAILED on exception
        logger.error(f"Exception in report generation {report_id}: {str(e)}")
        try:
            ReportCRUD.update_report_status(db, report_id, "FAILED")
        except:
            pass
        
        # Re-raise to trigger Celery retry
        raise e
    
    finally:
        # Clean up database connection
        try:
            db.close()
        except:
            pass
