import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
API_TITLE = "Social Agent Platform"
API_VERSION = "1.0.0"
DEFAULT_WORKFLOW_RETRY_LIMIT = int(os.getenv("WORKFLOW_RETRY_LIMIT", "3"))

# Local AI (Ollama) configuration — optional; falls back to template model.
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() not in {"0", "false", "no"}
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
