"""Disposable local API for Playwright. Uses scripted providers, never real AI."""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

root = Path(tempfile.mkdtemp(prefix="movewise-e2e-"))
os.environ.update({
    "DATABASE_URL": f"sqlite+pysqlite:///{(root / 'e2e.db').as_posix()}",
    "PRIVATE_UPLOAD_DIR": str(root / "uploads"),
    "EMBEDDING_PROVIDER": "mock",
    "LLM_PROVIDER": "mock-evaluation",
    "EVALUATION_MOCK_MODE": "true",
})

from alembic import command
from alembic.config import Config
from app.db.session import SessionLocal
from app.services.documents import process_one
from app.ai.providers.embedding import MockEmbeddings

config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
command.upgrade(config, "head")

def ingest_loop():
    while True:
        try:
            with SessionLocal() as db:
                worked = process_one(db, MockEmbeddings())
            if not worked:
                time.sleep(.25)
        except Exception as exc:
            print(f"E2E ingestion worker error: {type(exc).__name__}", flush=True)
            time.sleep(1)

threading.Thread(target=ingest_loop, daemon=True).start()

import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
