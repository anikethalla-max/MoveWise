from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.routes.v1 import workspace
from app.db.session import get_db
from app.db.models import Document, IngestionJob
from app.services.documents import save_upload, delete_document
from app.rag.retrieval import visible_documents
from app.ai.agents.document import answer_question
from app.core.config import settings
from app.core.rate_limit import ai_rate_limit, upload_rate_limit

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def describe(document: Document):
    return {"id": document.id, "name": document.name, "size_bytes": document.size_bytes,
            "visibility": document.visibility, "status": document.status, "error": document.error,
            "created_at": document.created_at}


@router.get("")
def list_documents(workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    return [describe(doc) for doc in visible_documents(db, workspace_id)]


@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...), workspace_id: str = Depends(workspace), db: Session = Depends(get_db), _:None=Depends(upload_rate_limit)):
    content = await file.read(settings.max_upload_bytes + 1)
    try:
        document = save_upload(db, workspace_id, file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return describe(document)


def owned_document(db: Session, workspace_id: str, document_id: str):
    document = db.scalar(select(Document).where(Document.id == document_id,
        Document.workspace_id == workspace_id, Document.visibility == "private"))
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get("/{document_id}")
def get_document(document_id: str, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    return describe(owned_document(db, workspace_id, document_id))


@router.post("/{document_id}/retry")
def retry_document(document_id: str, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    document = owned_document(db, workspace_id, document_id)
    if document.status not in ("failed", "ready"):
        raise HTTPException(409, "Document is already queued or processing")
    job = db.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id))
    job.status = document.status = "pending"
    job.error = document.error = None
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return describe(document)


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: str, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    delete_document(db, owned_document(db, workspace_id, document_id))


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None


@router.post("/questions/ask")
def ask_question(payload: QuestionInput, workspace_id: str = Depends(workspace), db: Session = Depends(get_db), _:None=Depends(ai_rate_limit)):
    try:
        return answer_question(db, workspace_id, payload.question, payload.document_ids)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, f"Document Agent unavailable: {str(exc)[:300]}") from exc
