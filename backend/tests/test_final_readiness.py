from datetime import timedelta
from tempfile import TemporaryDirectory
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from pydantic import ValidationError
from fastapi import HTTPException

from app.core.config import Settings, settings
from app.core.identity import workspace_for_identity
from app.core.rate_limit import WindowLimiter
from app.db.base import Base
from app.db.models import Workspace, AgentRun, Conversation
from app.services.documents import save_upload
from app.services.assistant_runs import recover_interrupted_runs, now


def memory_session():
    engine=create_engine('sqlite+pysqlite:///:memory:',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_production_requires_established_auth():
    try:
        Settings(_env_file=None,environment='production',auth_mode='development')
    except ValidationError as exc:
        assert 'AUTH_MODE=oidc' in str(exc)
    else:
        assert False, 'production accepted development identity'


def test_verified_identity_workspace_mapping():
    with memory_session() as db:
        first=workspace_for_identity(db,'https://issuer.example','subject-one')
        assert workspace_for_identity(db,'https://issuer.example','subject-one')==first
        assert workspace_for_identity(db,'https://issuer.example','subject-two')!=first
        assert workspace_for_identity(db,'https://other.example','subject-one')!=first


def test_rate_limit_and_upload_quota():
    limiter=WindowLimiter()
    limiter.check(('ai','workspace'),1,60)
    try:limiter.check(('ai','workspace'),1,60)
    except HTTPException as exc:assert exc.status_code==429
    else:assert False, 'rate limit not enforced'
    with memory_session() as db, TemporaryDirectory() as directory:
        workspace=Workspace();db.add(workspace);db.commit()
        old_path,old_max=settings.private_upload_dir,settings.max_workspace_upload_bytes
        settings.private_upload_dir=directory;settings.max_workspace_upload_bytes=5
        try:
            save_upload(db,workspace.id,'first.txt',b'1234')
            try:save_upload(db,workspace.id,'second.txt',b'12')
            except ValueError as exc:assert 'storage limit' in str(exc)
            else:assert False, 'upload quota not enforced'
        finally:
            settings.private_upload_dir=old_path;settings.max_workspace_upload_bytes=old_max


def test_interrupted_run_recovery_is_not_replayed():
    with memory_session() as db:
        workspace=Workspace();db.add(workspace);db.flush()
        conversation=Conversation(workspace_id=workspace.id,title='Interrupted request')
        db.add(conversation);db.flush()
        root=AgentRun(workspace_id=workspace.id,conversation_id=conversation.id,request='Test',agent='coordinator',
            status='running',updated_at=now()-timedelta(hours=1),created_at=now()-timedelta(hours=1))
        db.add(root);db.commit()
        assert recover_interrupted_runs(db)==1
        assert db.get(AgentRun,root.id).status=='failed'
        assert recover_interrupted_runs(db)==0
