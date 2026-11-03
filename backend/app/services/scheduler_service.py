import json
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from app.database import SessionLocal
from app.models.content import ContentItem

JOBSTORE_PATH = Path(__file__).resolve().parent.parent / "scheduler_jobs.db"
JOBSTORE_URL = f"sqlite:///{JOBSTORE_PATH}"

scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=JOBSTORE_URL)},
    timezone="UTC",
)


def _job_id_for(content_id: int) -> str:
    return f"content_{content_id}"


def execute_scheduled_publish(content_id: int) -> None:
    db = SessionLocal()
    try:
        content = db.query(ContentItem).filter(ContentItem.id == content_id).first()
        if not content:
            return
        content.status = "Published"
        content.published_at = datetime.utcnow()
        content.approval_notes = (content.approval_notes or "") + "\nLocal publishing simulation completed."
        db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    if not scheduler.running:
        scheduler.start()


def add_content_schedule(content_id: int, scheduled_for: datetime) -> None:
    job_id = _job_id_for(content_id)
    if scheduler.get_job(job_id):
        raise ValueError("This content item already has a scheduled job.")

    scheduler.add_job(
        execute_scheduled_publish,
        run_date=scheduled_for,
        id=job_id,
        args=[content_id],
        replace_existing=True,
    )


def remove_content_schedule(content_id: int) -> None:
    job_id = _job_id_for(content_id)
    job = scheduler.get_job(job_id)
    if job is not None:
        scheduler.remove_job(job_id)
