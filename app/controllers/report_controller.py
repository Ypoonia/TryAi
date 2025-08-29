#!/usr/bin/env python3
"""
Report Controller - Request/Response Handling Layer
Handles HTTP requests, validates input, calls services, formats responses
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from app.services.report_service import ReportService
from app.schemas.report import (
    ReportResponse,
    ReportStatusResponse,
    ReportDetailResponse,
    PendingStatusResponse,
    CurrentReportResponse
)

logger = logging.getLogger(__name__)


class ReportController:
    """
    Controller layer for report operations
    Handles request validation, service coordination, and response formatting
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.service = ReportService(db)
    
    def trigger_report(self) -> ReportResponse:
        """
        Controller: Handle report trigger request
        Validates business rules and returns appropriate response
        """
        try:
            # Call service layer for business logic
            result = self.service.create_new_report()
            
            if not result["success"]:
                # Handle different error scenarios
                error_code = result["error_code"]
                error_data = result["data"]
                
                if error_code == "CREATION_BLOCKED":
                    # Business rule violation - return 409 Conflict
                    existing_report = error_data.get("existing_report", {})
                    detail_msg = error_data.get("message", "Cannot create report")
                    
                    logger.warning(f"Report creation blocked: {detail_msg}")
                    raise HTTPException(status_code=409, detail=detail_msg)
                
                elif error_code == "CREATION_FAILED":
                    # Technical error - return 500 Internal Server Error
                    error_msg = error_data.get("message", "Internal error")
                    logger.error(f"Report creation failed: {error_msg}")
                    raise HTTPException(status_code=500, detail=f"Failed to create report: {error_msg}")
                
                else:
                    # Unknown error
                    logger.error(f"Unknown error creating report: {result}")
                    raise HTTPException(status_code=500, detail="Unknown error occurred")
            
            # Success case
            report_data = result["data"]
            logger.info(f"Report {report_data['report_id']} created successfully via controller")
            
            return ReportResponse(report_id=report_data["report_id"])
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            # Catch any unexpected errors
            logger.error(f"Unexpected error in trigger_report controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_report_status(self, report_id: str) -> ReportStatusResponse:
        """
        Controller: Handle get report status request
        Validates input and returns formatted response
        """
        try:
            # Input validation
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="report_id is required")
            
            # Call service layer
            result = self.service.get_report_by_id(report_id.strip())
            
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
            
            # Success case
            report_data = result["data"]
            logger.info(f"Report {report_id} status retrieved via controller: {report_data['status']}")
            
            return ReportStatusResponse(
                status=report_data["status"],
                report_id=report_id
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_report_status controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_report_details(self, report_id: str) -> ReportDetailResponse:
        """
        Controller: Handle get detailed report request
        Returns full report information
        """
        try:
            # Input validation
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="report_id is required")
            
            # Call service layer
            result = self.service.get_report_by_id(report_id.strip())
            
            if not result["success"]:
                error_code = result["error_code"]
                
                if error_code == "NOT_FOUND":
                    raise HTTPException(status_code=404, detail="report_id not found")
                else:
                    error_msg = result["data"].get("message", "Failed to fetch report")
                    raise HTTPException(status_code=500, detail=error_msg)
            
            # Success case
            report_data = result["data"]
            
            return ReportDetailResponse(
                report_id=report_data["report_id"],
                status=report_data["status"],
                url=report_data["url"],
                created_at=report_data["created_at"],
                updated_at=report_data["updated_at"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_report_details controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_pending_status(self) -> PendingStatusResponse:
        """
        Controller: Handle pending status check request
        """
        try:
            # Call service layer
            result = self.service.get_pending_report_status()
            
            if not result["success"]:
                error_data = result["data"]
                error_msg = error_data.get("message", "Failed to check pending status")
                logger.error(f"Error checking pending status: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            # Success case
            status_data = result["data"]
            
            return PendingStatusResponse(
                has_pending=status_data["has_pending"],
                report_id=status_data["report_id"],
                status=status_data["status"],
                created_at=status_data["created_at"],
                message=status_data["message"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_pending_status controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def get_current_report(self) -> CurrentReportResponse:
        """
        Controller: Handle current report request
        """
        try:
            # Call service layer
            result = self.service.get_current_report_from_json()
            
            if not result["success"]:
                error_data = result["data"]
                error_msg = error_data.get("message", "Failed to get current report")
                logger.error(f"Error getting current report: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            # Success case
            report_data = result["data"]
            
            # Handle datetime parsing for response
            created_at = None
            last_updated = None
            
            if report_data.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(report_data["created_at"])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid created_at format: {report_data.get('created_at')}")
            
            if report_data.get("last_updated"):
                try:
                    last_updated = datetime.fromisoformat(report_data["last_updated"])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid last_updated format: {report_data.get('last_updated')}")
            
            return CurrentReportResponse(
                current_report_id=report_data.get("current_report_id"),
                status=report_data.get("status"),
                created_at=created_at,
                last_updated=last_updated
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in get_current_report controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
    def update_report_status(self, report_id: str, new_status: str) -> ReportDetailResponse:
        """
        Controller: Handle report status update request
        """
        try:
            # Input validation
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="report_id is required")
            
            if not new_status or not new_status.strip():
                raise HTTPException(status_code=400, detail="status is required")
            
            # Call service layer
            result = self.service.update_report_status(report_id.strip(), new_status.strip())
            
            if not result["success"]:
                error_code = result["error_code"]
                error_data = result["data"]
                
                if error_code == "NOT_FOUND":
                    raise HTTPException(status_code=404, detail="report_id not found")
                elif error_code == "INVALID_STATUS":
                    raise HTTPException(status_code=400, detail=error_data.get("message"))
                else:
                    error_msg = error_data.get("message", "Failed to update report")
                    raise HTTPException(status_code=500, detail=error_msg)
            
            # Success case
            report_data = result["data"]
            
            return ReportDetailResponse(
                report_id=report_data["report_id"],
                status=report_data["status"],
                url=report_data["report"].url,
                created_at=report_data["report"].created_at,
                updated_at=report_data["updated_at"]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in update_report_status controller: {e}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
