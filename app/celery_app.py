from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "store_monitoring",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/0",
    include=["app.tasks.report_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

celery_app.conf.task_routes = {
    "app.tasks.report_tasks.generate_report": {"queue": "celery"},
}
