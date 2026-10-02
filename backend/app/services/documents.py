import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pypdf import PdfReader
from sqlalchemy import delete, or_, select, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.models import Document, DocumentChunk, IngestionJob
from app.ai.providers.embedding import embedding_provider

ALLOWED = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}


def upload_root() -> Path:
    root = Path(settings.private_upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_name(name: str) -> str:
    clean = Path(name.replace('\\', '/')).name
    clean = re.sub(r"[^A-Za-z0-9._ -]", "_", clean).strip(" .")
    if not clean or clean.startswith(".") or len(clean) > 255:
        raise ValueError("Invalid filename")
    if Path(clean).suffix.lower() not in ALLOWED:
        raise ValueError("Only PDF, TXT, and Markdown are supported")
    return clean


def validate_bytes(name: str, content: bytes) -> str:
    ext = Path(name).suffix.lower()
    if not content or len(content) > settings.max_upload_bytes:
        raise ValueError(f"File must be between 1 byte and {settings.max_upload_bytes} bytes")
    if ext == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("File is not a valid PDF")
    if ext != ".pdf":
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Text files must be UTF-8") from exc
        if b"\x00" in content:
            raise ValueError("Binary content is not supported")
    return ALLOWED[ext]


def save_upload(db: Session, workspace_id: str, filename: str, content: bytes) -> Document:
    name = safe_name(filename)
    content_type = validate_bytes(name, content)
    used=db.scalar(select(func.coalesce(func.sum(Document.size_bytes),0)).where(
        Document.workspace_id==workspace_id,Document.visibility=='private')) or 0
    if used+len(content)>settings.max_workspace_upload_bytes:
        raise ValueError('Workspace document storage limit reached')
    storage_name = f"{uuid.uuid4().hex}{Path(name).suffix.lower()}"
    path = upload_root() / storage_name
    path.write_bytes(content)
    try:
        document = Document(workspace_id=workspace_id, visibility="private", name=name,
            content_type=content_type, storage_name=storage_name, size_bytes=len(content), status="pending")
        db.add(document)
        db.flush()
        db.add(IngestionJob(document_id=document.id, status="pending", attempts=0, updated_at=datetime.now(timezone.utc)))
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise


def extract(document: Document) -> list[tuple[int | None, str | None, str]]:
    path = upload_root() / document.storage_name
    if document.content_type == "application/pdf":
        pages = [(index + 1, None, page.extract_text() or "") for index, page in enumerate(PdfReader(str(path)).pages)]
        if not any(text.strip() for _, _, text in pages):
            raise ValueError("No selectable text found. This scanned PDF needs OCR before upload.")
        return [(page, section, text) for page, section, text in pages if text.strip()]
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("Document contains no text")
    if document.content_type == "text/markdown":
        sections: list[tuple[int | None, str | None, str]] = []
        heading = "Start"
        current: list[str] = []
        for line in text.splitlines():
            if re.match(r"^#{1,6}\s+", line):
                if current:
                    sections.append((None, heading, "\n".join(current)))
                heading = line.lstrip("# ").strip()[:255]
                current = []
            else:
                current.append(line)
        if current:
            sections.append((None, heading, "\n".join(current)))
        return sections
    return [(None, "Text", text)]


def chunks(parts: list[tuple[int | None, str | None, str]], size: int = 1100, overlap: int = 150):
    for page, section, text in parts:
        text = re.sub(r"[ \t]+", " ", text).strip()
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                space = text.rfind(" ", start + size // 2, end)
                if space > start:
                    end = space
            excerpt = text[start:end].strip()
            if excerpt:
                yield page, section, excerpt
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)


def recover_interrupted(db: Session):
    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    for job in db.scalars(select(IngestionJob).where(IngestionJob.status == "processing", IngestionJob.updated_at < threshold)):
        job.status = "pending"
        document = db.get(Document, job.document_id)
        if document:
            document.status = "pending"
    db.commit()


def process_one(db: Session, provider=None) -> bool:
    recover_interrupted(db)
    job = db.scalar(select(IngestionJob).where(IngestionJob.status == "pending").order_by(IngestionJob.updated_at).with_for_update(skip_locked=True))
    if not job:
        return False
    document = db.get(Document, job.document_id)
    job.status = document.status = "processing"
    job.attempts += 1
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    try:
        extracted = list(chunks(extract(document)))
        if not extracted:
            raise ValueError("No text available for retrieval")
        vectors = (provider or embedding_provider()).embed([part[2] for part in extracted])
        if len(vectors) != len(extracted) or not vectors or any(not vector or len(vector)!=len(vectors[0]) for vector in vectors):
            raise ValueError("Embedding provider returned invalid dimensions")
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        for ordinal, ((page, section, text), vector) in enumerate(zip(extracted, vectors)):
            db.add(DocumentChunk(document_id=document.id, workspace_id=document.workspace_id,
                ordinal=ordinal, page=page, section=section, text=text, embedding=vector))
        document.status = job.status = "ready"
        document.error = job.error = None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(IngestionJob, job.id)
        document = db.get(Document, document.id)
        if job is None or document is None:
            return True  # Deleted while the worker was processing.
        document.status = job.status = "failed"
        document.error = job.error = str(exc)[:1000]
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    return True


def delete_document(db: Session, document: Document):
    path = upload_root() / document.storage_name
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.execute(delete(IngestionJob).where(IngestionJob.document_id == document.id))
    db.delete(document)
    db.commit()
    path.unlink(missing_ok=True)
