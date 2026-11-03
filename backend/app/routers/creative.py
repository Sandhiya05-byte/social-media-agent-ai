from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.agents.creative_generation_agent import CreativeGenerationAgent
from app.agents.video_production_agent import VideoProductionAgent
from app.schemas.creative import CreativeRequest, CreativeResponse

router = APIRouter(prefix="/api/creative", tags=["creative"])


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
def upload_authorized_media(file: UploadFile):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required.")

    uploads_dir = Path(__file__).resolve().parent.parent / "uploads" / "authorized"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    file_path = uploads_dir / file.filename
    with file_path.open("wb") as handle:
        handle.write(file.file.read())

    return {"status": "uploaded", "file_path": str(file_path)}


@router.get("/preview/{filename}")
def preview_generated_media(filename: str):
    image_dir = Path(__file__).resolve().parent.parent / "generated" / "creative"
    file_path = image_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path)
