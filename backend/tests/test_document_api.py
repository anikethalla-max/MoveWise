import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


def test_upload_validation_and_workspace_routes():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    def override():
        with Session() as db: yield db
    app.dependency_overrides[get_db]=override
    try:
        with tempfile.TemporaryDirectory() as directory:
            settings.private_upload_dir=directory
            with TestClient(app) as a, TestClient(app) as b:
                bad=a.post('/api/v1/documents',files={'file':('invalid.pdf',b'not a pdf','application/pdf')})
                assert bad.status_code==400
                uploaded=a.post('/api/v1/documents',files={'file':('agreement.txt',b'Deposit is refundable.','text/plain')})
                assert uploaded.status_code==201
                document_id=uploaded.json()['id']
                assert uploaded.json()['status']=='pending'
                assert len(a.get('/api/v1/documents').json())==1
                assert b.get('/api/v1/documents').json()==[]
                assert b.get(f'/api/v1/documents/{document_id}').status_code==404
                assert b.delete(f'/api/v1/documents/{document_id}').status_code==404
                assert b.post(f'/api/v1/documents/{document_id}/retry').status_code==404
                assert b.post('/api/v1/documents/questions/ask',json={'question':'Deposit?','document_ids':[document_id]}).status_code==400
                settings.openai_api_key=None
                assert a.post('/api/v1/documents/questions/ask',json={'question':'Deposit?'}).status_code==503
                assert a.delete(f'/api/v1/documents/{document_id}').status_code==204
                assert a.get('/api/v1/documents').json()==[]
    finally:
        app.dependency_overrides.pop(get_db,None)
