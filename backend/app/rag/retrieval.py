import math
import inspect
from sqlalchemy import or_, select, type_coerce
from sqlalchemy.orm import Session
from pgvector.sqlalchemy import Vector
from app.db.models import Document, DocumentChunk
from app.ai.providers.embedding import embedding_provider


def visible_documents(db: Session, workspace_id: str):
    return list(db.scalars(select(Document).where(or_(
        (Document.workspace_id == workspace_id) & (Document.visibility == "private"),
        (Document.workspace_id.is_(None)) & (Document.visibility == "shared-demo"))).order_by(Document.created_at.desc())))


def visible_document(db: Session, workspace_id: str, document_id: str) -> Document | None:
    return db.scalar(select(Document).where(Document.id == document_id, or_(
        (Document.workspace_id == workspace_id) & (Document.visibility == "private"),
        (Document.workspace_id.is_(None)) & (Document.visibility == "shared-demo"))))


def get_excerpt(db: Session, workspace_id: str, chunk_id: str):
    row = db.execute(select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.id == chunk_id, Document.status == "ready", or_(
            (Document.workspace_id == workspace_id) & (Document.visibility == "private"),
            (Document.workspace_id.is_(None)) & (Document.visibility == "shared-demo")))).first()
    return hit(*row) if row else None


def hit(chunk: DocumentChunk, document: Document, score: float | None = None):
    return {"chunk_id": chunk.id, "document_id": document.id, "document_name": document.name,
            "visibility": document.visibility, "page": chunk.page, "section": chunk.section,
            "excerpt": chunk.text, "score": score}


def search(db: Session, workspace_id: str, query: str, document_ids: list[str] | None = None,
           limit: int = 6, provider=None, limits=None):
    if not query.strip():
        raise ValueError("Search query is required")
    if document_ids is not None:
        selected = [visible_document(db, workspace_id, document_id) for document_id in set(document_ids)]
        if any(document is None for document in selected):
            raise ValueError("Selected document is unavailable")
        if not selected:
            return []
    embedder=provider or embedding_provider()
    kwargs={'timeout_seconds':limits.remaining_seconds()} if limits and 'timeout_seconds' in inspect.signature(embedder.embed).parameters else {}
    vector = embedder.embed([query],**kwargs)[0]
    criteria = [Document.status == "ready", or_(
        (Document.workspace_id == workspace_id) & (Document.visibility == "private"),
        (Document.workspace_id.is_(None)) & (Document.visibility == "shared-demo"))]
    if document_ids is not None:
        criteria.append(Document.id.in_(document_ids))
    statement = select(DocumentChunk, Document).join(Document, Document.id == DocumentChunk.document_id).where(*criteria)
    if db.bind.dialect.name == "postgresql":
        distance = type_coerce(DocumentChunk.embedding, Vector()).cosine_distance(vector)
        rows = db.execute(statement.order_by(distance).limit(limit)).all()
        return [hit(chunk, document) for chunk, document in rows]
    rows = db.execute(statement).all()
    def similarity(chunk):
        a, b = chunk.embedding, vector
        if len(a)!=len(b):
            raise ValueError('Stored document vectors use another embedding dimension; reprocess documents after changing models')
        denominator = math.sqrt(sum(x*x for x in a)) * math.sqrt(sum(x*x for x in b))
        return sum(x*y for x,y in zip(a,b)) / denominator if denominator else 0
    ranked = sorted(rows, key=lambda row: similarity(row[0]), reverse=True)[:limit]
    return [hit(chunk, document, similarity(chunk)) for chunk, document in ranked]
