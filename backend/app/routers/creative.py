from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.agents.creative_generation_agent import CreativeGenerationAgent
from app.agents.video_production_agent import VideoProductionAgent, sanitize_filename
from app.config import GENERATED_DIR, UPLOADS_DIR
from app.schemas.creative import CreativeRequest

router = APIRouter(prefix="/api/creative", tags=["creative"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _safe_generated_path(filename: str) -> Path:
    image_dir = GENERATED_DIR / "creative"
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="File name is required.")
    file_path = (image_dir / safe_name).resolve()
    if image_dir.resolve() not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid file path.")
    return file_path


@router.post("/generate", response_model=dict)
def generate_creative(payload: CreativeRequest):
    creative = CreativeGenerationAgent()
    image_result = creative.execute(
        title=payload.title,
        platform=payload.platform,
        content=payload.content,
        creator_media_path=payload.creator_image_path,
    )

    video = VideoProductionAgent()
    video_result = video.execute(
        title=payload.title,
        script=payload.script or payload.content or payload.title,
        platform=payload.platform,
        captions=payload.captions,
    )

    return {
        "status": "completed",
        "creative": image_result,
        "video": video_result,
    }


@router.post("/upload")
def upload_authorized_media(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required.")

    original_name = Path(file.filename).name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PNG, JPEG, WebP, or GIF creator media can be uploaded.",
        )

    contents = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded media exceeds the 25 MB limit.")

    safe_stem = sanitize_filename(Path(original_name).stem) or "creator_media"
    filename = f"{safe_stem}_{uuid.uuid4().hex[:8]}{extension}"

    uploads_dir = UPLOADS_DIR / "authorized"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / filename
    file_path.write_bytes(contents)

    return {
        "status": "uploaded",
        "file_path": str(file_path),
        "preview_url": f"/uploads/authorized/{filename}",
    }


@router.get("/preview/{filename}")
def preview_generated_media(filename: str):
    file_path = _safe_generated_path(filename)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path)
