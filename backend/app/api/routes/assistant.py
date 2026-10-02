import asyncio
import json
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.routes.v1 import workspace
from app.db.session import get_db, SessionLocal
from app.db.models import Conversation, AssistantMessage, AgentRun, RunEvent
from app.services.assistant_runs import create_run, execute_run, event_dict, run_dict, TERMINAL, now
from app.core.rate_limit import ai_rate_limit

router=APIRouter(prefix='/api/v1/assistant',tags=['assistant'])


class SendMessage(BaseModel):
    content:str=Field(min_length=1,max_length=4000)
    request_key:uuid.UUID
    conversation_id:str|None=None


def owned_conversation(db:Session,workspace_id:str,conversation_id:str):
    item=db.scalar(select(Conversation).where(Conversation.id==conversation_id,Conversation.workspace_id==workspace_id))
    if not item:raise HTTPException(404,'Conversation not found')
    return item


def owned_root_run(db:Session,workspace_id:str,run_id:str):
    item=db.scalar(select(AgentRun).where(AgentRun.id==run_id,AgentRun.workspace_id==workspace_id,
        AgentRun.parent_run_id.is_(None)))
    if not item:raise HTTPException(404,'Run not found')
    return item


@router.get('/conversations')
def conversations(workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    items=db.scalars(select(Conversation).where(Conversation.workspace_id==workspace_id).order_by(Conversation.created_at.desc())).all()
    return [{'id':c.id,'title':c.title,'created_at':c.created_at} for c in items]


@router.get('/conversations/{conversation_id}')
def conversation(conversation_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    item=owned_conversation(db,workspace_id,conversation_id)
    messages=db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id==item.id,
        AssistantMessage.workspace_id==workspace_id).order_by(AssistantMessage.created_at,AssistantMessage.id)).all()
    runs=db.scalars(select(AgentRun).where(AgentRun.conversation_id==item.id,
        AgentRun.workspace_id==workspace_id,AgentRun.parent_run_id.is_(None)).order_by(AgentRun.created_at)).all()
    return {'id':item.id,'title':item.title,'messages':[{'id':m.id,'role':m.role,'content':m.content,
        'payload':m.payload,'run_id':m.run_id,'created_at':m.created_at} for m in messages],
        'runs':[run_dict(r) for r in runs]}


@router.post('/messages',status_code=202)
def send_message(payload:SendMessage,background:BackgroundTasks,workspace_id:str=Depends(workspace),db:Session=Depends(get_db),_:None=Depends(ai_rate_limit)):
    try:run,created=create_run(db,workspace_id,payload.content,str(payload.request_key),payload.conversation_id)
    except ValueError as exc:raise HTTPException(404,str(exc)) from exc
    if created:background.add_task(execute_run,run.id)
    return {'run_id':run.id,'conversation_id':run.conversation_id,'created':created}


@router.get('/runs/{run_id}')
def get_run(run_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    root=owned_root_run(db,workspace_id,run_id)
    children=db.scalars(select(AgentRun).where(AgentRun.parent_run_id==run_id,
        AgentRun.workspace_id==workspace_id).order_by(AgentRun.created_at)).all()
    events=db.scalars(select(RunEvent).where(RunEvent.root_run_id==run_id,
        RunEvent.workspace_id==workspace_id).order_by(RunEvent.id)).all()
    return {'run':run_dict(root),'specialist_runs':[run_dict(c) for c in children],
            'events':[event_dict(e) for e in events]}


@router.post('/runs/{run_id}/cancel')
def cancel_run(run_id:str,workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    run=owned_root_run(db,workspace_id,run_id)
    if run.status not in TERMINAL:
        run.cancel_requested=True;run.updated_at=now();db.commit()
    return run_dict(run)


@router.get('/runs/{run_id}/events')
async def stream_events(request:Request,run_id:str,after:int=Query(default=0,ge=0),
                        last_event_id:str|None=Header(default=None,alias='Last-Event-ID'),
                        workspace_id:str=Depends(workspace),db:Session=Depends(get_db)):
    owned_root_run(db,workspace_id,run_id)
    try:cursor=max(after,int(last_event_id or 0))
    except ValueError:cursor=after
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            with SessionLocal() as stream_db:
                events=stream_db.scalars(select(RunEvent).where(RunEvent.root_run_id==run_id,
                    RunEvent.workspace_id==workspace_id,RunEvent.id>cursor).order_by(RunEvent.id).limit(100)).all()
                status=stream_db.scalar(select(AgentRun.status).where(AgentRun.id==run_id,
                    AgentRun.workspace_id==workspace_id))
                data=[event_dict(e) for e in events]
            for item in data:
                cursor=item['id']
                yield f"id: {cursor}\nevent: activity\ndata: {json.dumps(item)}\n\n"
            if status in TERMINAL:
                yield f"event: done\ndata: {json.dumps({'status':status})}\n\n"
                return
            yield ': keepalive\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
