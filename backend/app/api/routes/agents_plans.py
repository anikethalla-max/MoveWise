from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.api.routes.v1 import workspace
from app.db.session import get_db
from app.db.models import Housing, PlanVersion, PlanProposal, SelectedHome
from app.services.plans import current, plan_view, proposal_view, owned_proposal, confirm, cancel, set_completion, StaleProposal
from app.ai.agents.housing import advise
from app.ai.agents.planning import propose
from app.core.rate_limit import ai_rate_limit

router=APIRouter(prefix='/api/v1')


class AgentRequest(BaseModel):
    question: str = Field(min_length=1,max_length=2000)


@router.post('/agents/housing')
def housing_agent(payload:AgentRequest,workspace_id:str=Depends(workspace),db:Session=Depends(get_db),_:None=Depends(ai_rate_limit)):
    try: return advise(db,workspace_id,payload.question)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    except Exception as exc: raise HTTPException(503,f'Housing Agent unavailable: {str(exc)[:300]}') from exc


@router.post('/agents/planning')
def planning_agent(payload:AgentRequest,workspace_id:str=Depends(workspace),db:Session=Depends(get_db),_:None=Depends(ai_rate_limit)):
    try: return propose(db,workspace_id,payload.question)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    except Exception as exc: raise HTTPException(503,f'Planning Agent unavailable: {str(exc)[:300]}') from exc


class SelectionInput(BaseModel):
    home_id: str


@router.get('/selection/home')
def get_selected_home(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    selection=db.get(SelectedHome,workspace_id)
    if not selection:return None
    home=db.scalar(select(Housing).where(Housing.id==selection.housing_id,Housing.workspace_id==workspace_id))
    return {'home_id':home.id,'name':home.name} if home else None


@router.put('/selection/home')
def select_home(payload:SelectionInput,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    home=db.scalar(select(Housing).where(Housing.id==payload.home_id,Housing.workspace_id==workspace_id))
    if not home: raise HTTPException(404,'Housing option not found')
    selection=db.get(SelectedHome,workspace_id)
    if not selection: selection=SelectedHome(workspace_id=workspace_id,housing_id=home.id);db.add(selection)
    else:selection.housing_id=home.id
    db.commit()
    return {'home_id':home.id,'name':home.name}


@router.delete('/selection/home',status_code=204)
def clear_home(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    db.execute(delete(SelectedHome).where(SelectedHome.workspace_id==workspace_id));db.commit()


@router.get('/plans/current')
def current_plan(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    plan=current(db,workspace_id)
    return plan_view(db,plan) if plan else None


@router.get('/plans/history')
def plan_history(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    plans=db.scalars(select(PlanVersion).where(PlanVersion.workspace_id==workspace_id).order_by(PlanVersion.version.desc())).all()
    return [plan_view(db,plan) for plan in plans]


@router.get('/plans/proposals')
def proposals(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    items=db.scalars(select(PlanProposal).where(PlanProposal.workspace_id==workspace_id).order_by(PlanProposal.created_at.desc())).all()
    return [proposal_view(item) for item in items]


@router.get('/plans/proposals/{proposal_id}')
def proposal(proposal_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    try:return proposal_view(owned_proposal(db,workspace_id,proposal_id))
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc


@router.post('/plans/proposals/{proposal_id}/confirm')
def confirm_proposal(proposal_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    try:return plan_view(db,confirm(db,workspace_id,proposal_id))
    except StaleProposal as exc:raise HTTPException(409,str(exc)) from exc
    except ValueError as exc:raise HTTPException(404 if 'not found' in str(exc) else 409,str(exc)) from exc


@router.post('/plans/proposals/{proposal_id}/cancel')
def cancel_proposal(proposal_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    try:return cancel(db,workspace_id,proposal_id)
    except ValueError as exc:raise HTTPException(404 if 'not found' in str(exc) else 409,str(exc)) from exc


class CompletionInput(BaseModel):
    completed: bool


@router.put('/plans/tasks/{task_id}/completion')
def update_completion(task_id:str,payload:CompletionInput,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    try:return set_completion(db,workspace_id,task_id,payload.completed)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc
