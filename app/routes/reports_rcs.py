#!/usr/bin/env python3
"""
Report Routes - Simplified to 2 endpoints only
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.models import get_db
from app.controllers import ReportController
from app.schemas import ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_controller(db: Session = Depends(get_db)) -> ReportController:
    """Dependency to get Report Controller with database session"""
    return ReportController(db)


@router.post("/trigger_report", response_model=ReportResponse, summary="Trigger new report", status_code=202)
def trigger_report(controller: ReportController = Depends(get_report_controller)):
    """
    Trigger a new report generation
    
    **No input required**
    
    **Returns:**
    - report_id: Random string identifier for polling status
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8001/reports/trigger_report"
    ```
    """
    # Trigger comprehensive report (all stores) without the comprehensive parameter
    return controller.trigger_report(comprehensive=True)


@router.get("/get_report", summary="Get report status or CSV file")
def get_report(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """
    Get report status or download CSV file
    
    **Input:**
    - report_id: Report identifier from trigger_report
    
    **Output:**
    - If not complete: Returns "Running" status
    - If complete: Returns CSV file with schema:
      store_id, uptime_last_hour (minutes), uptime_last_day (hours), 
      uptime_last_week (hours), downtime_last_hour (minutes), 
      downtime_last_day (hours), downtime_last_week (hours)
    
    **Example:**
    ```bash
    curl "http://localhost:8001/reports/get_report?report_id=YOUR_REPORT_ID"
    ```
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
                headers={"Content-Disposition": f"attachment; filename={report_id}.csv"}
            )
        else:
            raise HTTPException(status_code=404, detail="Report file not found")
    
    # If complete but no URL
    return {"status": "Complete"}
