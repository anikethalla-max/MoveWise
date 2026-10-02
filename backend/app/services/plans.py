import uuid
import hashlib
import json
from datetime import date
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import Housing, Budget, Document, DocumentChunk, PlanVersion, PlanProposal, Profile, SelectedHome, TaskCompletion
from app.services.housing_compare import calculate


class PlanTask(BaseModel):
    id: str | None = None
    title: str = Field(min_length=3,max_length=200)
    stage: str
    due_date: date | None = None
    priority: str
    category: str = Field(min_length=2,max_length=80)
    source_kind: str = 'general'
    citation_chunk_ids: list[str] = Field(default_factory=list)

    @field_validator('stage')
    @classmethod
    def stage_valid(cls,value):
        if value not in {'before-moving','moving-day','after-moving'}: raise ValueError('Invalid stage')
        return value

    @field_validator('priority')
    @classmethod
    def priority_valid(cls,value):
        if value not in {'high','medium','low'}: raise ValueError('Invalid priority')
        return value

    @field_validator('source_kind')
    @classmethod
    def source_valid(cls,value):
        if value not in {'general','document'}: raise ValueError('Invalid source kind')
        return value


class PlanCandidate(BaseModel):
    summary: str = Field(min_length=5,max_length=2000)
    tasks: list[PlanTask] = Field(min_length=1,max_length=80)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class StaleProposal(ValueError):
    pass


def current(db:Session,workspace_id:str,lock:bool=False):
    query=select(PlanVersion).where(PlanVersion.workspace_id==workspace_id).order_by(PlanVersion.version.desc()).limit(1)
    if lock and db.bind.dialect.name=='postgresql': query=query.with_for_update()
    return db.scalar(query)


def selected_home(db:Session,workspace_id:str):
    selection=db.get(SelectedHome,workspace_id)
    if not selection: return None
    return db.scalar(select(Housing).where(Housing.id==selection.housing_id,Housing.workspace_id==workspace_id))


def context_hash(db:Session,workspace_id:str):
    profile=db.scalar(select(Profile).where(Profile.workspace_id==workspace_id))
    budget=db.scalar(select(Budget).where(Budget.workspace_id==workspace_id))
    home=selected_home(db,workspace_id)
    def fields(item,names):
        return {name:str(getattr(item,name)) if getattr(item,name) is not None else None for name in names} if item else None
    data={'profile':fields(profile,['destination_city','workplace_area','moving_date','monthly_limit','upfront_limit','household_size','housing_preferences','commute_preferences']),
          'budget':fields(budget,['rent','maintenance','utilities','food','transport','miscellaneous','deposit','moving_costs','setup_costs']),
          'selected_home':fields(home,['id','name','locality','rent','maintenance','deposit','furnishing','notes','commute_minutes'])}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def plan_view(db:Session,plan:PlanVersion):
    completion={row.task_id:row.completed for row in db.scalars(select(TaskCompletion).where(TaskCompletion.workspace_id==plan.workspace_id))}
    return {'id':plan.id,'version':plan.version,'summary':plan.summary,
        'tasks':[{**task,'completed':completion.get(task['id'],False)} for task in plan.tasks],
        'budget_concerns':plan.budget_concerns,'assumptions':plan.assumptions,
        'missing_information':plan.missing_information,'citations':plan.citations,
        'created_at':plan.created_at}


def budget_concerns(db:Session,workspace_id:str):
    home=selected_home(db,workspace_id)
    result=calculate(db,workspace_id,home.id if home else None)
    concerns=[]
    if result['monthly_affordable'] is False:
        concerns.append(f"Known monthly total ₹{result['monthly_total']} exceeds limit ₹{result['monthly_limit']}.")
    elif result['monthly_affordable'] is None:
        concerns.append('Monthly affordability is unknown until all costs and the limit are entered.')
    if result['upfront_affordable'] is False:
        concerns.append(f"Known upfront total ₹{result['upfront_total']} exceeds limit ₹{result['upfront_limit']}.")
    elif result['upfront_affordable'] is None:
        concerns.append('Upfront affordability is unknown until deposit, moving/setup costs, and the limit are entered.')
    return concerns


def normalize_candidate(db:Session,workspace_id:str,candidate:PlanCandidate,retrieved:dict):
    profile=db.scalar(select(Profile).where(Profile.workspace_id==workspace_id))
    base=current(db,workspace_id)
    old_tasks=base.tasks if base else []
    old_by_id={task['id']:task for task in old_tasks}
    old_by_key={(task['stage'],task['title'].strip().lower()):task['id'] for task in old_tasks}
    seen=set();tasks=[];citations={}
    for task in candidate.tasks:
        if task.source_kind=='document' and not task.citation_chunk_ids:
            raise ValueError('Document-dependent task requires a citation')
        if task.source_kind=='general' and task.citation_chunk_ids:
            raise ValueError('General task cannot carry document citations')
        for chunk_id in task.citation_chunk_ids:
            if chunk_id not in retrieved: raise ValueError('Plan cited a chunk not retrieved during this run')
            citations[chunk_id]=retrieved[chunk_id]
        if profile and profile.moving_date and task.due_date:
            if task.stage=='before-moving' and task.due_date>profile.moving_date: raise ValueError('Before-moving task is due after move date')
            if task.stage=='moving-day' and task.due_date!=profile.moving_date: raise ValueError('Moving-day task must use move date')
            if task.stage=='after-moving' and task.due_date<profile.moving_date: raise ValueError('After-moving task is due before move date')
        if task.id and task.id not in old_by_id:
            raise ValueError('Unknown task ID in revision')
        task_id=task.id or old_by_key.get((task.stage,task.title.strip().lower())) or str(uuid.uuid4())
        if task_id in seen: raise ValueError('Duplicate task')
        seen.add(task_id)
        item=task.model_dump(mode='json');item['id']=task_id
        tasks.append(item)
    if not profile or not profile.moving_date:
        if any(task['due_date'] for task in tasks): raise ValueError('Set a moving date before assigning due dates')
        if not any('date' in item.lower() for item in candidate.missing_information):
            raise ValueError('Moving date must be listed as missing')
    return {'summary':candidate.summary,'tasks':tasks,'budget_concerns':budget_concerns(db,workspace_id),
            'assumptions':candidate.assumptions,'missing_information':candidate.missing_information,
            'citations':list(citations.values())}


def diff(old:list,new:list):
    before={task['id']:task for task in old};after={task['id']:task for task in new}
    return {'additions':[task for tid,task in after.items() if tid not in before],
            'removals':[task for tid,task in before.items() if tid not in after],
            'edits':[{'before':before[tid],'after':task} for tid,task in after.items() if tid in before and task!=before[tid]]}


def create_proposal(db:Session,workspace_id:str,candidate:PlanCandidate,retrieved:dict):
    normalized=normalize_candidate(db,workspace_id,candidate,retrieved)
    base=current(db,workspace_id)
    proposal=PlanProposal(workspace_id=workspace_id,base_version=base.version if base else 0,
        context_hash=context_hash(db,workspace_id),
        status='pending',candidate=normalized,changes=diff(base.tasks if base else [],normalized['tasks']))
    db.add(proposal);db.commit();db.refresh(proposal)
    return proposal_view(proposal)


def proposal_view(proposal:PlanProposal):
    return {'id':proposal.id,'base_version':proposal.base_version,'status':proposal.status,
        'candidate':proposal.candidate,'changes':proposal.changes,
        'applied_version':proposal.applied_version,'created_at':proposal.created_at}


def owned_proposal(db:Session,workspace_id:str,proposal_id:str):
    proposal=db.scalar(select(PlanProposal).where(PlanProposal.id==proposal_id,PlanProposal.workspace_id==workspace_id))
    if not proposal: raise ValueError('Proposal not found')
    return proposal


def cancel(db:Session,workspace_id:str,proposal_id:str):
    proposal=owned_proposal(db,workspace_id,proposal_id)
    if proposal.status=='confirmed': raise ValueError('Confirmed proposal cannot be cancelled')
    if proposal.status=='pending': proposal.status='cancelled';db.commit()
    return proposal_view(proposal)


def confirm(db:Session,workspace_id:str,proposal_id:str):
    proposal=owned_proposal(db,workspace_id,proposal_id)
    if db.bind.dialect.name=='postgresql':
        proposal=db.scalar(select(PlanProposal).where(PlanProposal.id==proposal_id,PlanProposal.workspace_id==workspace_id).with_for_update())
    if proposal.status=='confirmed':
        return db.scalar(select(PlanVersion).where(PlanVersion.workspace_id==workspace_id,PlanVersion.version==proposal.applied_version))
    if proposal.status!='pending': raise ValueError('Proposal was cancelled')
    base=current(db,workspace_id,lock=True)
    if (base.version if base else 0)!=proposal.base_version: raise StaleProposal('Proposal is stale. Generate a new revision.')
    if context_hash(db,workspace_id)!=proposal.context_hash:
        raise StaleProposal('Profile, budget, or selected home changed. Generate a new revision.')
    for citation in proposal.candidate['citations']:
        chunk=db.scalar(select(DocumentChunk).join(Document,Document.id==DocumentChunk.document_id).where(
            DocumentChunk.id==citation['chunk_id'], Document.status=='ready',
            ((Document.workspace_id==workspace_id) & (Document.visibility=='private')) |
            ((Document.workspace_id.is_(None)) & (Document.visibility=='shared-demo'))))
        if chunk is None: raise StaleProposal('A cited document changed or was removed. Generate a new revision.')
    data=proposal.candidate
    plan=PlanVersion(workspace_id=workspace_id,version=proposal.base_version+1,
        summary=data['summary'],tasks=data['tasks'],budget_concerns=data['budget_concerns'],
        assumptions=data['assumptions'],missing_information=data['missing_information'],citations=data['citations'])
    db.add(plan)
    proposal.status='confirmed';proposal.applied_version=plan.version
    db.commit();db.refresh(plan)
    return plan


def set_completion(db:Session,workspace_id:str,task_id:str,completed:bool):
    plan=current(db,workspace_id)
    if not plan or task_id not in {task['id'] for task in plan.tasks}: raise ValueError('Task not found in current plan')
    row=db.get(TaskCompletion,{'workspace_id':workspace_id,'task_id':task_id})
    if not row: row=TaskCompletion(workspace_id=workspace_id,task_id=task_id);db.add(row)
    row.completed=completed;db.commit()
    return {'task_id':task_id,'completed':completed}
