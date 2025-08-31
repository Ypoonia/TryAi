#!/usr/bin/env python3
"""
Report Controller - Request/Response Handling Layer
Handles HTTP requests, validates input, calls services, formats responses
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
import logging

from app.services.report_service import ReportService
from app.schemas.report import ReportResponse, ReportStatusResponse

logger = logging.getLogger(__name__)


class ReportController:
    """Controller for report operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.service = ReportService(db)
    
    def trigger_report(self, comprehensive: bool = False) -> ReportResponse:
        """Handle report trigger request"""
        try:
            result = self.service.create_new_report(comprehensive)
            
            if not result["success"]:
                error_code = result["error_code"]
                error_data = result["data"]
                
                if error_code == "CREATION_BLOCKED":
                    detail_msg = error_data.get("message", "Cannot create report")
                    logger.warning(f"Report creation blocked: {detail_msg}")
                    raise HTTPException(status_code=409, detail=detail_msg)
                
                elif error_code == "CREATION_FAILED":
                    error_msg = error_data.get("message", "Internal error")
                    logger.error(f"Report creation failed: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Failed to create report: {error_msg}")
                
                else:
                    logger.error(f"Unknown error creating report: {result}")
                    raise HTTPException(status_code=500, detail="Unknown error occurred")
            
            report_data = result["data"]
            report_id = report_data["report_id"]
            
            # Set to RUNNING status
            self.service.set_report_status_and_url(report_id, "RUNNING")
            
            logger.info(f"Report {report_id} created and set to RUNNING")
            
            return ReportResponse(report_id=report_id, status="RUNNING")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in trigger_report: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_report_status(self, report_id: str) -> ReportStatusResponse:
        """Handle get report status request"""
        try:
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="report_id is required")
            
            result = self.service.get_report_with_url_logic(report_id.strip())
            
            if not result["success"]:
                error_code = result["error_code"]
                error_data = result["data"]
                
                if error_code == "NOT_FOUND":
                    logger.warning(f"Report {report_id} not found")
                    raise HTTPException(status_code=404, detail="report_id not found")
                
                elif error_code == "FETCH_FAILED":
                    error_msg = error_data.get("message", "Failed to fetch report")
                    logger.error(f"Error fetching report {report_id}: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Failed to get report: {error_msg}")
                
                else:
                    logger.error(f"Unknown error fetching report {report_id}: {result}")
                    raise HTTPException(status_code=500, detail="Unknown error occurred")
            
            report_data = result["data"]
            logger.info(f"Report {report_id} status retrieved: {report_data['status']}")
            
            return ReportStatusResponse(
                status=report_data["status"],
                report_id=report_id,
                url=report_data["url"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_report_status: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
