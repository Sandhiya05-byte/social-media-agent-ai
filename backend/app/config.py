import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'app.db'}")
API_TITLE = "Social Agent Platform"
API_VERSION = "1.0.0"
DEFAULT_WORKFLOW_RETRY_LIMIT = int(os.getenv("WORKFLOW_RETRY_LIMIT", "3"))
