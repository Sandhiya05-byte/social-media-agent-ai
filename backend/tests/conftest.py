from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="social_agent_tests_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TEST_STATE_DIR / 'test.db').as_posix()}"
os.environ["SCHEDULER_JOBSTORE_PATH"] = str(TEST_STATE_DIR / "scheduler_jobs.db")
os.environ["OLLAMA_ENABLED"] = "false"
