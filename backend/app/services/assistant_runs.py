import json
import time
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Conversation, AssistantMessage, AgentRun, RunEvent
from app.core.config import settings
from app.ai.agents.runtime import SharedLimits, AgentCancelled, AgentLimitError
from app.ai.agents.coordinator import coordinate

TERMINAL={'completed','partial','failed','cancelled'}


def now():return datetime.now(timezone.utc)


def create_run(db:Session,workspace_id:str,content:str,request_key:str,conversation_id:str|None=None):
    existing=db.scalar(select(AgentRun).where(AgentRun.workspace_id==workspace_id,AgentRun.request_key==request_key))
    if existing:return existing,False
    if conversation_id:
        conversation=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.workspace_id==workspace_id))
        if not conversation:raise ValueError('Conversation not found')
    else:
        conversation=Conversation(workspace_id=workspace_id,title=content.strip()[:160]);db.add(conversation);db.flush()
    run=AgentRun(conversation_id=conversation.id,workspace_id=workspace_id,parent_run_id=None,
        request_key=request_key,agent='coordinator',status='queued',request=content,cancel_requested=False,
        created_at=now(),updated_at=now())
    db.add(run);db.flush()
    db.add(AssistantMessage(conversation_id=conversation.id,workspace_id=workspace_id,run_id=run.id,
        role='user',content=content,created_at=now()))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(AgentRun).where(AgentRun.workspace_id==workspace_id,AgentRun.request_key==request_key))
        if existing:return existing,False
        raise
    db.refresh(run)
    return run,True


def event_dict(event:RunEvent):
    return {'id':event.id,'root_run_id':event.root_run_id,'agent_run_id':event.agent_run_id,
        'event_type':event.event_type,'agent':event.agent,'tool_name':event.tool_name,
        'status':event.status,'summary':event.summary,'details':event.details,
        'created_at':event.created_at.isoformat()}


def run_dict(run:AgentRun):
    return {'id':run.id,'conversation_id':run.conversation_id,'parent_run_id':run.parent_run_id,
        'agent':run.agent,'status':run.status,'request':run.request,'result':run.result,'error':run.error,
        'cancel_requested':run.cancel_requested,'created_at':run.created_at,'updated_at':run.updated_at}


def execute_run(run_id:str,llm_factory=None,embedder=None,limits_config=None):
    with SessionLocal() as db:
        claim=select(AgentRun).where(AgentRun.id==run_id,AgentRun.parent_run_id.is_(None))
        if db.bind.dialect.name=='postgresql':claim=claim.with_for_update(skip_locked=True)
        root=db.scalar(claim)
        if not root or root.status!='queued':return
        root.status='running';root.updated_at=now();db.commit()
        def emit(**kwargs):
            event=RunEvent(root_run_id=root.id,agent_run_id=kwargs['agent_run_id'] or root.id,
                workspace_id=root.workspace_id,event_type=kwargs['event_type'],agent=kwargs['agent'] or 'coordinator',
                tool_name=kwargs.get('tool_name'),status=kwargs['status'],summary=kwargs['summary'][:300],
                details=kwargs.get('details') or {},created_at=now())
            db.add(event);db.commit()
        def cancelled():
            db.refresh(root)
            return root.cancel_requested
        configured={'max_tool_steps':settings.run_max_tool_steps,'max_seconds':settings.run_max_seconds,
            'max_tokens':settings.run_max_tokens}
        configured.update(limits_config or {})
        limits=SharedLimits(cancel_check=cancelled,event=emit,**configured)
        started=time.monotonic()
        try:
            limits.check()
            emit(agent_run_id=root.id,agent='coordinator',event_type='run',tool_name=None,
                status='running',summary='Coordinator started',details={'run_id':root.id})
            result=coordinate(db,root,limits,llm_factory=llm_factory,embedder=embedder)
            limits.check()
            cost=None
            if settings.llm_input_usd_per_1m is not None and settings.llm_output_usd_per_1m is not None and (limits.provider_prompt_tokens or limits.provider_completion_tokens):
                cost=str((Decimal(limits.provider_prompt_tokens)*settings.llm_input_usd_per_1m+
                    Decimal(limits.provider_completion_tokens)*settings.llm_output_usd_per_1m)/Decimal(1000000))
            result['usage']={'provider_prompt_tokens':limits.provider_prompt_tokens or None,
                'provider_completion_tokens':limits.provider_completion_tokens or None,
                'conservative_token_estimate':limits.token_estimate,'estimated_llm_cost_usd':cost}
            result['latency_ms']=round((time.monotonic()-started)*1000)
            root.status=result['status'];root.result=json.loads(json.dumps(result,default=str))
            root.updated_at=now()
            db.add(AssistantMessage(conversation_id=root.conversation_id,workspace_id=root.workspace_id,
                run_id=root.id,role='assistant',content=result['answer'],payload=root.result,created_at=now()))
            db.commit()
            emit(agent_run_id=root.id,agent='coordinator',event_type='run',tool_name=None,
                status=root.status,summary='Coordinator finished',details={'tool_steps':limits.tool_steps,
                    'token_estimate':limits.token_estimate})
        except Exception as exc:
            db.rollback();root=db.get(AgentRun,run_id)
            children=list(db.scalars(select(AgentRun).where(AgentRun.parent_run_id==run_id).order_by(AgentRun.created_at)))
            partial=[{'agent':c.agent,'run_id':c.id,'status':c.status,'result':c.result} for c in children]
            cancelled_run=isinstance(exc,AgentCancelled) or root.cancel_requested
            root.status='cancelled' if cancelled_run else 'partial' if any(c.status=='completed' for c in children) else 'failed'
            root.error=f'{exc.__class__.__name__}: run stopped'  # No private text or credentials in logs.
            root.result={'answer':'The request stopped before all work completed.',
                'citations':[citation for item in partial if item['agent']=='document' and item.get('result')
                    for citation in item['result'].get('citations',[])],
                'missing_information':['Some agent work did not complete.'],
                'conflicts':[],'specialist_results':partial,'activity':[],'status':root.status,
                'latency_ms':round((time.monotonic()-started)*1000),
                'usage':{'provider_prompt_tokens':limits.provider_prompt_tokens or None,
                    'provider_completion_tokens':limits.provider_completion_tokens or None,
                    'conservative_token_estimate':limits.token_estimate,'estimated_llm_cost_usd':None}}
            root.updated_at=now()
            if root.status!='cancelled':
                db.add(AssistantMessage(conversation_id=root.conversation_id,workspace_id=root.workspace_id,
                    run_id=root.id,role='assistant',content=root.result['answer'],payload=root.result,created_at=now()))
            db.commit()
            emit(agent_run_id=root.id,agent='coordinator',event_type='run',tool_name=None,
                status=root.status,summary='Coordinator stopped',details={'error_type':exc.__class__.__name__,
                    'tool_steps':limits.tool_steps,'token_estimate':limits.token_estimate})


def recover_interrupted_runs(db:Session):
    threshold=now()-timedelta(seconds=settings.run_max_seconds+60)
    roots=list(db.scalars(select(AgentRun).where(AgentRun.parent_run_id.is_(None),
        AgentRun.status=='running',AgentRun.updated_at<threshold)))
    for root in roots:
        children=list(db.scalars(select(AgentRun).where(AgentRun.parent_run_id==root.id)))
        for child in children:
            if child.status=='running':child.status='failed';child.error='Interrupted by server restart';child.updated_at=now()
        root.status='failed';root.error='Interrupted by server restart; run was not replayed';root.updated_at=now()
        root.result={'answer':'This run was interrupted and was not replayed.',
            'citations':[],'missing_information':['Run interrupted; start a new request if needed.'],
            'conflicts':[],'specialist_results':[{'agent':c.agent,'run_id':c.id,'status':c.status,
                'result':c.result} for c in children],'activity':[],'status':'failed'}
        db.add(RunEvent(root_run_id=root.id,agent_run_id=root.id,workspace_id=root.workspace_id,
            event_type='run',agent='coordinator',status='failed',summary='Run interrupted',
            details={'reason':'server_restart'},created_at=now()))
    db.commit()
    return len(roots)
