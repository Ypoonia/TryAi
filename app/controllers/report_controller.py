#!/usr/bin/env python3
"""
HTTP controller for reports with clean orchestration.
- Minimal HTTP logic: validation, service calls, response formatting.
- Let service layer handle all business logic.
- Proper error handling and status codes.
"""

import logging
from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.report_service import ReportService, ReportServiceError
from app.schemas.report import ReportResponse, ReportStatusResponse

logger = logging.getLogger(__name__)


class ReportController:
    """HTTP orchestration for report endpoints"""

    @staticmethod
    def trigger_report(db: Session) -> Dict[str, Any]:
        """
        Trigger report generation endpoint.
        Returns 202 for new reports, 200 for existing active reports.
        """
        try:
            result = ReportService.trigger_report(db)
            
            # Determine HTTP status code
            if result.message == "Report generation already in progress":
                status_code = 200
                headers = {"Retry-After": "30"}  # Check again in 30 seconds
            else:
                status_code = 202  # Accepted for processing
                headers = {"Retry-After": "60"}  # Initial processing time estimate
            
            logger.info(
                "Report trigger endpoint response",
                extra={
                    "report_id": result.report_id,
                    "status": result.status.value,
                    "http_status": status_code,
                },
            )
            
            return {
                "status_code": status_code,
                "headers": headers,
                "body": {
                    "report_id": result.report_id,
                    "status": result.status.value,
                    "message": result.message,
                },
            }
            
        except ReportServiceError as e:
            logger.error("Service error in trigger endpoint", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Service error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in trigger endpoint")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    def get_report_status(db: Session, report_id: str) -> Dict[str, Any]:
        """
        Get report status endpoint.
        Returns current status with appropriate headers for polling.
        """
        try:
            # Input validation
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="Report ID is required")
            
            result = ReportService.get_report_status(db, report_id.strip())
            
            # Set polling headers based on status
            headers = {}
            if result.status.value in ["PENDING", "RUNNING"]:
                headers["Retry-After"] = "15"  # Poll every 15 seconds for active reports
            
            logger.debug(
                "Report status endpoint response",
                extra={
                    "report_id": report_id,
                    "status": result.status.value,
                    "has_url": result.url is not None,
                },
            )
            
            # Build response body
            body = {
                "report_id": result.report_id,
                "status": result.status.value,
            }
            
            # Only include URL for completed reports
            if result.url:
                body["url"] = result.url
            
            return {
                "status_code": 200,
                "headers": headers,
                "body": body,
            }
            
        except ReportServiceError as e:
            if "not found" in str(e).lower():
                logger.warning("Report not found", extra={"report_id": report_id})
                raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
            else:
                logger.error("Service error in status endpoint", extra={"error": str(e)})
                raise HTTPException(status_code=500, detail=f"Service error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in status endpoint")
            raise HTTPException(status_code=500, detail="Internal server error")
