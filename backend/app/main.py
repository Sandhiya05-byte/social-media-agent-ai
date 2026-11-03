from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import API_TITLE, API_VERSION
from app.database import init_db
from app.routers.content import router as content_router
from app.routers.creator import router as creator_router
from app.routers.creative import router as creative_router
from app.routers.research import router as research_router
from app.services.scheduler_service import start_scheduler

app = FastAPI(title=API_TITLE, version=API_VERSION)

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

init_db()
app.include_router(content_router)
app.include_router(creator_router)
app.include_router(research_router)
app.include_router(creative_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "social-agent-backend", "version": API_VERSION}


@app.on_event("startup")
def startup_event():
    init_db()
    start_scheduler()
