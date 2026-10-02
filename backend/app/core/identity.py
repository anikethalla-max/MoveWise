from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.models import Workspace


def workspace_for_identity(db:Session,issuer:str,subject:str)->str:
    if not issuer or not subject or len(issuer)>255 or len(subject)>255:
        raise ValueError('Invalid verified identity')
    item=db.scalar(select(Workspace).where(Workspace.identity_issuer==issuer,Workspace.identity_subject==subject))
    if item:return item.id
    item=Workspace(identity_issuer=issuer,identity_subject=subject)
    db.add(item)
    try:db.commit()
    except IntegrityError:
        db.rollback()
        item=db.scalar(select(Workspace).where(Workspace.identity_issuer==issuer,Workspace.identity_subject==subject))
        if not item:raise
    return item.id
