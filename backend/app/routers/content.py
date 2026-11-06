from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import GENERATED_DIR
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
from app.time_utils import to_naive_utc, utcnow

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
    except (json.JSONDecodeError, TypeError):
        return [value]
    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    return [str(parsed)]


def _media_urls(item: ContentItem) -> dict:
    """Derive frontend-loadable media URLs from the stored media_path."""
    media_path = item.media_path or ""
    urls = {"media_url": None, "thumbnail_url": None, "subtitle_url": None}
    if not media_path:
        return urls
    if media_path.startswith("/") or media_path.startswith(("http://", "https://")):
        urls["media_url"] = media_path
        # Web URLs under /generated map into GENERATED_DIR, so sibling
        # thumbnail and subtitle assets can still be derived.
        relative = media_path.split("/generated/", 1)[-1]
        try:
            resolved = (GENERATED_DIR / relative).resolve()
            if GENERATED_DIR.resolve() in resolved.parents or resolved.parent == GENERATED_DIR.resolve():
                thumbnail = resolved.with_name(f"{resolved.stem}_thumb.png")
                if thumbnail.exists():
                    urls["thumbnail_url"] = f"/generated/{thumbnail.relative_to(GENERATED_DIR).as_posix()}"
                subtitle = resolved.with_suffix(".srt")
                if subtitle.exists():
                    urls["subtitle_url"] = f"/generated/{subtitle.relative_to(GENERATED_DIR).as_posix()}"
        except (ValueError, OSError):
            pass
        return urls
    # Absolute filesystem path inside GENERATED_DIR -> web URL.
    try:
        generated_root = GENERATED_DIR.resolve()
        resolved = Path(media_path).resolve()
        if resolved.parent == generated_root or generated_root in resolved.parents:
            urls["media_url"] = f"/generated/{resolved.relative_to(generated_root).as_posix()}"
            thumbnail = resolved.with_name(f"{resolved.stem}_thumb.png")
            if thumbnail.exists():
                urls["thumbnail_url"] = f"/generated/{thumbnail.relative_to(generated_root).as_posix()}"
            subtitle = resolved.with_suffix(".srt")
            if subtitle.exists():
                urls["subtitle_url"] = f"/generated/{subtitle.relative_to(generated_root).as_posix()}"
    except (ValueError, OSError):
        pass
    return urls


def _serialize_content(item: ContentItem) -> dict:
    serialized = {
        "id": item.id,
        "title": item.title,
        "platform": item.platform,
        "content": item.content,
        "script": item.script,
        "captions": _as_list(item.captions),
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
        "workflow_id": item.workflow_id,
        "generation_source": item.generation_source,
    }
    serialized.update(_media_urls(item))
    return serialized


from app.models.creator import Creator  # noqa: E402  (used by approval sync below)


@router.post("/from-workflow/{workflow_id}", response_model=ContentRead, status_code=status.HTTP_201_CREATED)
def create_content_from_workflow(workflow_id: int, db: Session = Depends(get_db)):
    """Bridge an approved-completed workflow's generated content into the
    Content Studio approval queue.

    Workflow approval and content approval stay distinct: this only copies
    the generated creative output into a persistent ContentItem awaiting
    human review. It never auto-approves.
    """
    from app.orchestration.execution_manager import ExecutionManager

    manager = ExecutionManager()
    workflow = manager.get_workflow(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found.")

    context = manager.get_workflow_context(workflow_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Workflow checkpoint not found.")

    creative = context.creative_output or {}
    video = context.video_output or {}
    title = str(creative.get("title") or context.campaign_topic or "").strip()
    content = str(creative.get("content") or "").strip()
    if not title or not content:
        raise HTTPException(status_code=409, detail="Workflow has no generated creative content to review yet.")

    # The MP4 URL is the reviewable media; fall back to the raw video path
    # only when the agent did not produce a web URL.
    media_path = video.get("video_url") or video.get("video_path") or creative.get("preview_url")

    # Bridge is idempotent by workflow_id: the auto-bridge may already have
    # created the item, so a manual repeat must not duplicate it.
    existing = db.query(ContentItem).filter(ContentItem.workflow_id == workflow_id).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="This workflow's content is already in the approval queue.")

    validation = validate_content_payload(
        {
            "title": title,
            "platform": context.platforms[0] if context.platforms else "Instagram",
            "content": content,
            "script": creative.get("script"),
            "captions": creative.get("captions", []),
            "media_path": media_path,
        }
    )
    content_item = ContentItem(
        title=title[:180],
        platform=context.platforms[0] if context.platforms else "Instagram",
        content=content,
        script=creative.get("script"),
        captions=json.dumps(creative.get("captions", [])),
        media_path=media_path,
        validation_errors=json.dumps(validation.errors),
        validation_warnings=json.dumps(validation.warnings),
        status="Awaiting Approval" if not validation.errors else "Validation Failed",
    )
    db.add(content_item)
    db.commit()
    db.refresh(content_item)
    return _serialize_content(content_item)


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


def _sync_workflow_approval(db: Session, item: ContentItem, status: str, approved_by: str | None, notes: str | None) -> None:
    """Keep the originating workflow's approval state in sync with the ContentItem.

    Workflow approval and content approval are distinct decisions, but once a
    ContentItem is linked to a workflow the workflow's approval status mirrors
    the content decision so downstream gates stay consistent.
    """
    if not item.workflow_id:
        return
    from app.orchestration.execution_manager import ExecutionManager

    mapping = {
        "Approved": "APPROVED",
        "Rejected": "REJECTED",
        "Draft": "REQUESTED_CHANGES",
        "Awaiting Approval": "PENDING",
    }
    workflow_status = mapping.get(status)
    if not workflow_status:
        return
    try:
        content_hash = None
        if workflow_status == "APPROVED":
            content_hash = _content_fingerprint_for_workflow(item.workflow_id)
        ExecutionManager().record_approval_decision(
            item.workflow_id,
            workflow_status,
            approved_by=approved_by,
            notes=notes,
            content_hash=content_hash,
            session=db,
        )
    except Exception:
        pass  # workflow may not exist (manually created content)


def _content_fingerprint_for_workflow(workflow_id: int):
    from app.orchestration.workflow_engine import WorkflowEngine

    context = ExecutionManager().get_workflow_context(workflow_id)
    if context is None:
        return None
    return WorkflowEngine()._content_fingerprint(context)
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

@router.post("/{content_id}/approve", response_model=ContentRead)
def approve_content(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Approved"
    item.approved_by = payload.approved_by or "creator"
    item.approved_at = utcnow()
    item.approval_notes = payload.notes or item.approval_notes
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    _sync_workflow_approval(db, item, item.status, item.approved_by, item.approval_notes)
    return _serialize_content(item)


@router.post("/{content_id}/reject", response_model=ContentRead)
def reject_content(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Rejected"
    item.approval_notes = payload.notes or item.approval_notes or "Rejected by reviewer."
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    _sync_workflow_approval(db, item, item.status, None, item.approval_notes)
    return _serialize_content(item)


@router.post("/{content_id}/request-changes", response_model=ContentRead)
def request_changes(content_id: int, payload: ContentApprovalRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")

    item.status = "Draft"
    item.approval_notes = payload.notes or item.approval_notes or "Changes requested by reviewer."
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)


@router.post("/{content_id}/schedule", response_model=ContentRead)
def schedule_content(content_id: int, payload: ScheduleRequest, db: Session = Depends(get_db)):
    item = db.query(ContentItem).filter(ContentItem.id == content_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Content item not found.")
    if item.status == "Scheduled":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Content item #{item.id} ('{item.title}') already has a scheduled job "
                f"for {item.scheduled_for}. Cancel or reschedule it first."
            ),
        )
    if item.status != "Approved":
        raise HTTPException(status_code=400, detail="Only approved content can be scheduled.")

    # Publication permission: the owning creator must be approved for
    # publication before anything can be scheduled.
    if item.creator_id is not None:
        creator = db.get(Creator, item.creator_id)
        if creator is not None and not creator.approved_for_publication:
            raise HTTPException(
                status_code=403,
                detail="Creator is not approved for publication. Enable publication permission before scheduling.",
            )

    scheduled_for = to_naive_utc(payload.scheduled_for)
    try:
        add_content_schedule(item.id, scheduled_for)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Content item #{item.id} ('{item.title}') already has a scheduled job "
                f"for {item.scheduled_for}. Cancel or reschedule it first."
            ),
        ) from exc

    item.status = "Scheduled"
    item.scheduled_for = scheduled_for
    item.updated_at = utcnow()
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
    item.updated_at = utcnow()
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

    previous_schedule = item.scheduled_for
    scheduled_for = to_naive_utc(payload.scheduled_for)
    remove_content_schedule(item.id)
    try:
        add_content_schedule(item.id, scheduled_for)
    except Exception as exc:
        if previous_schedule is not None:
            try:
                add_content_schedule(item.id, previous_schedule)
            except Exception:
                pass
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    item.status = "Scheduled"
    item.scheduled_for = scheduled_for
    item.updated_at = utcnow()
    db.commit()
    db.refresh(item)
    return _serialize_content(item)
