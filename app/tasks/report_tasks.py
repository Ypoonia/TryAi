import logging
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.celery_app import celery_app
from app.services.compute_Algo import MinuteIndexReportService
from app.database.crud import ReportCRUD
from app.schemas.report import ReportStatus
from app.core.config import settings

logger = logging.getLogger(__name__)

_engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@celery_app.task(bind=True, name="app.tasks.report_tasks.generate_report")
def generate_report(self, report_id: str, max_stores: int = 50_000):
    logger.info("Starting async report generation", extra={"report_id": report_id, "max_stores": max_stores})

    db = None
    try:
        db = SessionLocal()

        rpt = ReportCRUD.get_report_by_id(db, report_id)
        if not rpt:
            logger.warning("Report not found for task; nothing to do", extra={"report_id": report_id})
            return {
                "success": False,
                "report_id": report_id,
                "error": "report_not_found",
                "timestamp": datetime.utcnow().isoformat(),
            }

        if rpt.status in (ReportStatus.COMPLETE.value, ReportStatus.FAILED.value):
            logger.info(
                "Report already in terminal state; skipping generation",
                extra={"report_id": report_id, "status": rpt.status},
            )
            return {
                "success": rpt.status == ReportStatus.COMPLETE.value,
                "report_id": report_id,
                "file_url": rpt.url,
                "status": rpt.status,
                "timestamp": datetime.utcnow().isoformat(),
            }

        if rpt.status == ReportStatus.PENDING.value:
            ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.RUNNING)
            logger.info("Report moved to RUNNING", extra={"report_id": report_id})

        gen = MinuteIndexReportService(db)
        result = gen.generate_store_report(report_id, max_stores=max_stores)

        if result.get("success"):
            file_path = result["file_path"]
            internal_url = file_path if file_path.startswith("file://") else f"file://{file_path}"

            ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.COMPLETE, internal_url)
            logger.info("Report generation completed", extra={"report_id": report_id, "file_url": internal_url})

            return {
                "success": True,
                "report_id": report_id,
                "file_url": internal_url,
                "total_stores": result.get("total_stores"),
                "completed_at": datetime.utcnow().isoformat(),
            }

        error_msg = result.get("error", "Unknown error")
        ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.FAILED)
        logger.error("Report generation failed", extra={"report_id": report_id, "error": error_msg})

        return {
            "success": False,
            "report_id": report_id,
            "error": error_msg,
            "failed_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.exception("Unhandled exception in report generation", extra={"report_id": report_id})
        try:
            if db is not None:
                ReportCRUD.set_report_status_and_url(db, report_id, ReportStatus.FAILED)
        except Exception:
            logger.exception("Failed to mark report as FAILED after exception", extra={"report_id": report_id})
        raise

    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass
