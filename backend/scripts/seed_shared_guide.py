"""Add a read-only synthetic guide visible to all local workspaces."""
from pathlib import Path
from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models import Document, IngestionJob
from app.services.documents import upload_root

name = 'bengaluru-moving-guide.md'
source = Path(__file__).resolve().parents[2] / 'data' / 'demo' / name
content = source.read_bytes()
with SessionLocal() as db:
    if db.scalar(select(Document).where(Document.visibility == 'shared-demo', Document.name == name)):
        print('Synthetic guide already exists.')
    else:
        storage_name = 'shared-synthetic-bengaluru-guide.md'
        (upload_root() / storage_name).write_bytes(content)
        document = Document(workspace_id=None, visibility='shared-demo', name=name,
            content_type='text/markdown', storage_name=storage_name,
            size_bytes=len(content), status='pending')
        db.add(document); db.flush()
        db.add(IngestionJob(document_id=document.id, status='pending', attempts=0))
        db.commit()
        print('Synthetic guide queued. Run the document worker to process it.')
