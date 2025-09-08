import logging
from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.report_service import ReportService, ReportNotFound, RepositoryError
from app.schemas.report import ReportResponse, ReportStatusResponse

logger = logging.getLogger(__name__)


class ReportController:

    @staticmethod
    def trigger_report(db: Session) -> Dict[str, Any]:
        try:
            service = ReportService(db)
            report_id = service.trigger()
            
            logger.info(
                "Report trigger endpoint response",
                extra={"report_id": report_id},
            )
            
            return {
                "status_code": 202,
                "headers": {"Retry-After": "60"},
                "body": {
                    "report_id": report_id,
                    "status": "PENDING",
                    "message": "Report generation started",
                },
            }
            
        except RepositoryError as e:
            logger.error("Repository error in trigger endpoint", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in trigger endpoint")
            raise HTTPException(status_code=500, detail="Internal server error")

    @staticmethod
    def get_report_status(db: Session, report_id: str) -> Dict[str, Any]:
        try:
            if not report_id or not report_id.strip():
                raise HTTPException(status_code=400, detail="Report ID is required")
            
            service = ReportService(db)
            status, public_url = service.get_status_with_public_url(report_id.strip())
            
            headers = {}
            if status == "Running":
                headers["Retry-After"] = "15"
            
            logger.debug(
                "Report status endpoint response",
                extra={
                    "report_id": report_id,
                    "status": status,
                    "has_url": public_url is not None,
                },
            )
            
            body = {
                "report_id": report_id,
                "status": status,
            }
            
            if public_url:
                body["url"] = public_url
            
            return {
                "status_code": 200,
                "headers": headers,
                "body": body,
            }
            
        except ReportNotFound:
            logger.warning("Report not found", extra={"report_id": report_id})
            raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
        except RepositoryError as e:
            logger.error("Repository error in status endpoint", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in status endpoint")
            raise HTTPException(status_code=500, detail="Internal server error")
