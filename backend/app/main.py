from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import API_TITLE, API_VERSION, GENERATED_DIR, UPLOADS_DIR
from app.database import init_db
from app.routers.content import router as content_router
from app.routers.creator import router as creator_router
from app.routers.creative import router as creative_router
from app.routers.dashboard import router as dashboard_router
from app.routers.orchestration import router as orchestration_router
from app.routers.research import router as research_router
from app.services.scheduler_service import shutdown_scheduler, start_scheduler

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

init_db()
app.include_router(content_router)
app.include_router(creator_router)
app.include_router(dashboard_router)
app.include_router(research_router)
app.include_router(creative_router)
app.include_router(orchestration_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "social-agent-backend", "version": API_VERSION}
