import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
GENERATED_DIR = Path(os.getenv("GENERATED_DIR", str(BASE_DIR / "generated")))
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", str(BASE_DIR / "uploads")))
API_TITLE = "Social Agent Platform"
API_VERSION = "1.0.0"
DEFAULT_WORKFLOW_RETRY_LIMIT = int(os.getenv("WORKFLOW_RETRY_LIMIT", "3"))

# Local AI (Ollama) configuration — optional; falls back to template model.
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() not in {"0", "false", "no"}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "240"))

# Research providers — all optional, configured via environment only.
BROWSER_SERVICE_URL = os.getenv("BROWSER_SERVICE_URL", "http://127.0.0.1:8002").rstrip("/")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "").strip()
GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
GOOGLE_SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CSE_ID", "").strip()

_default_feeds = "https://feeds.bbci.co.uk/news/technology/rss.xml,https://www.theverge.com/rss/index.xml,https://techcrunch.com/feed/"
RSS_FEEDS = [f.strip() for f in os.getenv("RESEARCH_RSS_FEEDS", _default_feeds).split(",") if f.strip()]
