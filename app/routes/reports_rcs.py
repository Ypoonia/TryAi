#!/usr/bin/env python3
"""
FastAPI routes for report endpoints with proper HTTP handling.
- Clean route definitions with dependency injection.
- Proper HTTP status codes and headers.
- Structured error handling.
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.controllers.report_controller import ReportController
from app.models.base import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/trigger_report")
async def trigger_report(
    response: Response,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Trigger report generation.
    
    Returns:
        - 202: New report started
        - 200: Existing active report found
        - 500: Server error
    
    Headers:
        - Retry-After: Suggested polling interval in seconds
    """
    result = ReportController.trigger_report(db)
    
    # Set HTTP status and headers
    response.status_code = result["status_code"]
    for key, value in result["headers"].items():
        response.headers[key] = str(value)
    
    return result["body"]


@router.get("/get_report/{report_id}")
async def get_report_status(
    report_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get report status and download URL.
    
    Args:
        report_id: Unique report identifier
    
    Returns:
        - 200: Report status retrieved
        - 404: Report not found
        - 400: Invalid report ID
        - 500: Server error
    
    Headers:
        - Retry-After: Suggested polling interval for active reports
    """
    result = ReportController.get_report_status(db, report_id)
    
    # Set HTTP status and headers
    response.status_code = result["status_code"]
    for key, value in result["headers"].items():
        response.headers[key] = str(value)
    
    return result["body"]
    
