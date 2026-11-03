import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.content import ContentItem
from app.schemas.content import (
    ContentApprovalRequest,
    ContentCreate,
    ContentRead,
    ContentValidationRequest,
    ScheduleRequest,
    ValidationResult,
)
from app.services.content_validation import validate_content_payload
from app.services.scheduler_service import add_content_schedule, remove_content_schedule

router = APIRouter(prefix="/api/content", tags=["content"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _as_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except json.JSONDecodeError:
        return [value]


def _serialize_content(item: ContentItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "platform": item.platform,
        "content": item.content,
        "script": item.script,
        "captions": json.loads(item.captions) if item.captions else [],
        "media_path": item.media_path,
        "status": item.status,
        "validation_errors": _as_list(item.validation_errors),
        "validation_warnings": _as_list(item.validation_warnings),
        "approval_notes": item.approval_notes,
        "approved_by": item.approved_by,
        "approved_at": item.approved_at,
        "scheduled_for": item.scheduled_for,
        "published_at": item.published_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.post("/validate", response_model=ValidationResult)
def validate_content(payload: ContentValidationRequest):
    return validate_content_payload(payload)


@router.post("", response_model=ContentRead, status_code=status.HTTP_201_CREATED)
def create_content(payload: ContentCreate, db: Session = Depends(get_db)):
    validation = validate_content_payload(payload)
    content = ContentItem(
        title=payload.title,
        platform=payload.platform,
        content=payload.content,
        script=payload.script,
        captions=json.dumps(payload.captions),
        media_path=payload.media_path,
        validation_errors=json.dumps(validation.errors),
        validation_warnings=json.dumps(validation.warnings),
        status="Awaiting Approval" if not validation.errors else "Validation Failed",
    )
    db.add(content)
    db.commit()
    db.refresh(content)
    return _serialize_content(content)


@router.get("", response_model=list[ContentRead])
def list_content(db: Session = Depends(get_db)):
    items = db.query(ContentItem).order_by(ContentItem.created_at.desc()).all()
    return [_serialize_content(item) for item in items]


@router.get("/{content_id}", response_model=ContentRead)
def get_content(content_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")
    return _serialize_content(item)


@router.post("/{content_id}/approve", response_model=ContentRead)
def approve_content(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Approved"
    item.approved_by = payload.approved_by or "creator"
    item.approved_at = datetime.utcnow()
    item.approval_notes = payload.notes or item.approval_notes
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/reject", response_model=ContentRead)
def reject_content(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Rejected"
    item.approval_notes = payload.notes or item.approval_notes or "Rejected by reviewer."
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/request-changes", response_model=ContentRead)
def request_changes(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Draft"
    item.approval_notes = payload.notes or item.approval_notes or "Changes requested by reviewer."
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/schedule", response_model=ContentRead)
def schedule_content(content_id: int, payload: ScheduleRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")
    if item.status == "Scheduled":
        raise HTTPException(status_code=409, detail="This content item already has a scheduled job.")
    if item.status != "Approved":
        raise HTTPException(status_code=400, detail="Only approved content can be scheduled.")

    try:
        add_content_schedule(item.id, payload.scheduled_for)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    item.status = "Scheduled"
    item.scheduled_for = payload.scheduled_for
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/cancel-schedule", response_model=ContentRead)
def cancel_schedule(content_id: int, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    remove_content_schedule(item.id)
    item.status = "Approved" if item.status == "Scheduled" else item.status
    item.scheduled_for = None
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/reschedule", response_model=ContentRead)
def reschedule_content(content_id: int, payload: ScheduleRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")
    if item.status not in {"Approved", "Scheduled"}:
        raise HTTPException(status_code=400, detail="Only approved or scheduled content can be rescheduled.")

    remove_content_schedule(item.id)
    add_content_schedule(item.id, payload.scheduled_for)
    item.status = "Scheduled"
    item.scheduled_for = payload.scheduled_for
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)
