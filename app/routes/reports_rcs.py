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
    result = ReportController.trigger_report(db)
    
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
    result = ReportController.get_report_status(db, report_id)
    
    response.status_code = result["status_code"]
    for key, value in result["headers"].items():
        response.headers[key] = str(value)
    
    return result["body"]
    
