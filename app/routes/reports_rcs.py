#!/usr/bin/env python3
"""
Report Routes - Using Routes-Controller-Service Architecture
This demonstrates proper separation of concerns with clean architecture
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.models import get_db
from app.controllers import ReportController
from app.schemas import (
    ReportResponse,
    ReportStatusResponse,
    ReportDetailResponse,
    PendingStatusResponse,
    CurrentReportResponse
)

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_controller(db: Session = Depends(get_db)) -> ReportController:
    """Dependency to get Report Controller with database session"""
    return ReportController(db)


@router.post("/trigger", response_model=ReportResponse, summary="Trigger new report", status_code=202)
def trigger_report(controller: ReportController = Depends(get_report_controller)):
    """
    Trigger a new report generation
    
    **Business Rules:**
    - Only one PENDING report allowed at a time
    - Generates unique timestamp-based report ID
    - Automatically sets status to RUNNING
    
    **Returns:**
    - 202: {report_id, status:"RUNNING"}
    
    **Errors:**
    - 409: PENDING/RUNNING report already exists (with existing report_id)
    - 500: Internal server error
    """
    return controller.trigger_report()


@router.get("/status", response_model=ReportStatusResponse, summary="Get report status")
def get_report_status(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Get current status of a specific report
    
    **Parameters:**
    - report_id: Unique report identifier
    
    **Returns:**
    - status: Current report status (PENDING/RUNNING/COMPLETE/FAILED)
    - report_id: The requested report ID
    
    **Errors:**
    - 400: Invalid or missing report_id
    - 404: Report not found
    - 500: Internal server error
    """
    return controller.get_report_status(report_id)


@router.get("/get_report", summary="Get report status or download CSV file")
def get_report(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Get report status or download CSV file
    
    **Parameters:**
    - report_id: Unique report identifier
    
    **Returns:**
    - If report is not complete: Returns "Running" status
    - If report is complete: Returns the CSV file with the schema:
      store_id, uptime_last_hour (minutes), uptime_last_day (hours), 
      uptime_last_week (hours), downtime_last_hour (minutes), 
      downtime_last_day (hours), downtime_last_week (hours)
    
    **Errors:**
    - 400: Invalid or missing report_id
    - 404: Report not found
    - 500: Internal server error
    """
    # Get report status
    status_result = controller.get_report_status(report_id)
    
    # If not complete, return "Running"
    if status_result.status not in ["COMPLETE", "COMPLETED"]:
        return {"status": "Running"}
    
    # If complete, return the CSV content
    if status_result.url:
        # Extract file path from URL
        file_path = status_result.url.replace("file://", "")
        if file_path.startswith("/"):
            file_path = file_path[1:]  # Remove leading slash
        
        # Check if file exists and read CSV content
        import os
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={"Content-Disposition": f"inline; filename={report_id}.csv"}
            )
        else:
            raise HTTPException(status_code=404, detail="Report file not found")
    
    # If complete but no URL
    raise HTTPException(status_code=500, detail="Report complete but file not available")


@router.get("/details", response_model=ReportDetailResponse, summary="Get detailed report info")
def get_report_details(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Get detailed information about a specific report
    
    **Parameters:**
    - report_id: Unique report identifier
    
    **Returns:**
    - Complete report information including timestamps and URL
    
    **Errors:**
    - 400: Invalid or missing report_id
    - 404: Report not found
    - 500: Internal server error
    """
    return controller.get_report_details(report_id)


@router.get("/current", response_model=CurrentReportResponse, summary="Get current active report")
def get_current_report(controller: ReportController = Depends(get_report_controller)):
    """
    Get current active report from JSON tracking
    
    **Returns:**
    - Information about the most recently triggered report
    - null values if no active report
    
    **Errors:**
    - 500: Internal server error reading JSON file
    """
    return controller.get_current_report()


@router.get("/pending", response_model=PendingStatusResponse, summary="Check for pending reports")
def get_pending_status(controller: ReportController = Depends(get_report_controller)):
    """
    Check if there are any PENDING reports in the system
    
    **Returns:**
    - has_pending: Boolean indicating if PENDING report exists
    - report_id: ID of the PENDING report (if any)
    - Details about the PENDING report
    
    **Errors:**
    - 500: Internal server error
    """
    return controller.get_pending_status()


@router.put("/status", response_model=ReportDetailResponse, summary="Update report status")
def update_report_status(
    report_id: str,
    new_status: str,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Update the status of an existing report
    
    **Parameters:**
    - report_id: Unique report identifier
    - new_status: New status (PENDING/RUNNING/COMPLETE/FAILED)
    
    **Business Rules:**
    - Status must be one of the valid values
    - Completed/Failed reports are removed from JSON tracking
    
    **Returns:**
    - Updated report details
    
    **Errors:**
    - 400: Invalid report_id or status
    - 404: Report not found
    - 500: Internal server error
    """
    return controller.update_report_status(report_id, new_status)


@router.put("/complete", response_model=ReportDetailResponse, summary="Complete report with URL")
def complete_report_with_url(
    report_id: str,
    status: str,
    url: str = None,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Update report status and URL (for compute workers)
    
    **Parameters:**
    - report_id: Unique report identifier
    - status: New status (RUNNING/COMPLETE/FAILED)
    - url: Report output URL (optional, typically for COMPLETE status)
    
    **Business Rules:**
    - URL should typically only be provided for COMPLETE status
    - Completed/Failed reports are removed from JSON tracking
    - URL visibility follows business rules (only shown when COMPLETE)
    
    **Returns:**
    - Updated report details with URL
    
    **Errors:**
    - 400: Invalid report_id or status
    - 404: Report not found
    - 500: Internal server error
    
    **Example Usage for Compute Workers:**
    ```bash
    # Mark as RUNNING when compute starts
    curl -X PUT "http://localhost:8001/reports/complete?report_id=123&status=RUNNING"
    
    # Mark as COMPLETE with URL when done
    curl -X PUT "http://localhost:8001/reports/complete?report_id=123&status=COMPLETE&url=file:///path/to/report.json"
    ```
    """
    return controller.set_report_status_and_url(report_id, status, url)


# ============================================
# LEGACY ENDPOINTS (Backward Compatibility)
# ============================================

@router.post("/trigger_report", response_model=ReportResponse, include_in_schema=False)
def trigger_report_legacy(controller: ReportController = Depends(get_report_controller)):
    """Legacy endpoint - use POST /reports/trigger instead"""
    return controller.trigger_report()


@router.get("/get_report", response_model=ReportStatusResponse, include_in_schema=False)
def get_report_legacy(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """Legacy endpoint - use GET /reports/status instead"""
    return controller.get_report_status(report_id)


@router.get("/current_report", response_model=CurrentReportResponse, include_in_schema=False)
def get_current_report_legacy(controller: ReportController = Depends(get_report_controller)):
    """Legacy endpoint - use GET /reports/current instead"""
    return controller.get_current_report()


@router.get("/pending_status", response_model=PendingStatusResponse, include_in_schema=False)
def get_pending_status_legacy(controller: ReportController = Depends(get_report_controller)):
    """Legacy endpoint - use GET /reports/pending instead"""
    return controller.get_pending_status()
