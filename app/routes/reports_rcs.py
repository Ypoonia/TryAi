#!/usr/bin/env python3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.models import get_db
from app.controllers import ReportController
from app.schemas import ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_controller(db: Session = Depends(get_db)) -> ReportController:
    """Get controller with database session"""
    return ReportController(db)


@router.post("/trigger_report", response_model=ReportResponse, summary="Trigger new report", status_code=202)
def trigger_report(controller: ReportController = Depends(get_report_controller)):
    """Start generating a new store report"""
    return controller.trigger_report()


@router.get("/get_report", summary="Get report status or CSV file")
def get_report(
    report_id: str,
    controller: ReportController = Depends(get_report_controller)
):
    """Get report status or download CSV when ready"""
    status_result = controller.get_report_status(report_id)
    
    if status_result.status == "COMPLETED":
        return {"status": "Complete", "url": status_result.url}
    elif status_result.status == "FAILED":
        return {"status": "Failed"}
    else:
        return {"status": "Running"}
    
