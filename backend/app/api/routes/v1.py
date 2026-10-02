from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, Request
from sqlalchemy import select
from sqlalchemy import delete
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Workspace, Profile, Housing, Budget, SelectedHome
from app.core.config import settings
from app.core.identity import workspace_for_identity
from app.schemas.records import ProfileInput, ProfileOut, HousingInput, HousingOut, BudgetInput, BudgetOut, budget_out

router = APIRouter(prefix="/api/v1")
COOKIE = "movewise_session"


def workspace(response: Response, request:Request, db: Session = Depends(get_db), token: str | None = Cookie(default=None, alias=COOKIE)) -> str:
    # Random workspace ID is an opaque local session; never supplied by the LLM or request body.
    if settings.auth_mode=='oidc':
        identity=request.session.get('identity')
        if not identity or identity.get('iss')!=settings.oidc_issuer or not identity.get('sub'):
            raise HTTPException(401,'Sign in required')
        return workspace_for_identity(db,identity['iss'],identity['sub'])
    if token and len(token) == 36:
        item = db.get(Workspace, token)
        if item:
            return item.id
    item = Workspace()
    db.add(item)
    db.commit()
    db.refresh(item)
    response.set_cookie(COOKIE, item.id, httponly=True, samesite="lax", secure=False, max_age=60 * 60 * 24 * 30)
    return item.id


@router.post("/session")
def create_session(workspace_id: str = Depends(workspace)):
    return {"ready": True}


@router.get("/profile", response_model=ProfileOut | None)
def get_profile(workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    return db.scalar(select(Profile).where(Profile.workspace_id == workspace_id))


@router.put("/profile", response_model=ProfileOut)
def put_profile(payload: ProfileInput, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    item = db.scalar(select(Profile).where(Profile.workspace_id == workspace_id))
    if item is None:
        item = Profile(workspace_id=workspace_id)
        db.add(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.get("/housing", response_model=list[HousingOut])
def list_housing(workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    return db.scalars(select(Housing).where(Housing.workspace_id == workspace_id).order_by(Housing.name)).all()


@router.post("/housing", response_model=HousingOut, status_code=201)
def create_housing(payload: HousingInput, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    item = Housing(workspace_id=workspace_id, source="user-entered", **payload.model_dump(mode="json"))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def owned_housing(item_id: str, workspace_id: str, db: Session) -> Housing:
    item = db.scalar(select(Housing).where(Housing.id == item_id, Housing.workspace_id == workspace_id))
    if item is None:
        raise HTTPException(404, "Housing option not found")
    return item


@router.get("/housing/{item_id}", response_model=HousingOut)
def get_housing(item_id: str, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    return owned_housing(item_id, workspace_id, db)


@router.put("/housing/{item_id}", response_model=HousingOut)
def put_housing(item_id: str, payload: HousingInput, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    item = owned_housing(item_id, workspace_id, db)
    for key, value in payload.model_dump(mode="json").items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/housing/{item_id}", status_code=204)
def delete_housing(item_id: str, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    db.execute(delete(SelectedHome).where(SelectedHome.workspace_id == workspace_id, SelectedHome.housing_id == item_id))
    db.delete(owned_housing(item_id, workspace_id, db))
    db.commit()


@router.get("/budget", response_model=BudgetOut)
def get_budget(workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    item = db.scalar(select(Budget).where(Budget.workspace_id == workspace_id))
    return budget_out(BudgetInput.model_validate(item, from_attributes=True) if item else BudgetInput())


@router.put("/budget", response_model=BudgetOut)
def put_budget(payload: BudgetInput, workspace_id: str = Depends(workspace), db: Session = Depends(get_db)):
    item = db.scalar(select(Budget).where(Budget.workspace_id == workspace_id))
    if item is None:
        item = Budget(workspace_id=workspace_id)
        db.add(item)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    db.commit()
    return budget_out(payload)
