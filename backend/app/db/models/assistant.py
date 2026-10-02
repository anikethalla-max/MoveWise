from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from .records import uid


def now(): return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__='conversations'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    title:Mapped[str]=mapped_column(String(160))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class AssistantMessage(Base):
    __tablename__='assistant_messages'
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id'),index=True)
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    run_id:Mapped[str|None]=mapped_column(ForeignKey('agent_runs.id'))
    role:Mapped[str]=mapped_column(String(20))
    content:Mapped[str]=mapped_column(Text)
    payload:Mapped[dict|None]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class AgentRun(Base):
    __tablename__='agent_runs'
    __table_args__=(UniqueConstraint('workspace_id','request_key',name='uq_run_request_key'),)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    conversation_id:Mapped[str]=mapped_column(ForeignKey('conversations.id'),index=True)
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    parent_run_id:Mapped[str|None]=mapped_column(ForeignKey('agent_runs.id'),index=True)
    request_key:Mapped[str|None]=mapped_column(String(80))
    agent:Mapped[str]=mapped_column(String(30))
    status:Mapped[str]=mapped_column(String(20),default='queued')
    request:Mapped[str]=mapped_column(Text)
    result:Mapped[dict|None]=mapped_column(JSON)
    error:Mapped[str|None]=mapped_column(Text)
    cancel_requested:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class RunEvent(Base):
    __tablename__='run_events'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    root_run_id:Mapped[str]=mapped_column(ForeignKey('agent_runs.id'),index=True)
    agent_run_id:Mapped[str]=mapped_column(ForeignKey('agent_runs.id'),index=True)
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    event_type:Mapped[str]=mapped_column(String(30))
    agent:Mapped[str]=mapped_column(String(30))
    tool_name:Mapped[str|None]=mapped_column(String(80))
    status:Mapped[str]=mapped_column(String(20))
    summary:Mapped[str]=mapped_column(String(300))
    details:Mapped[dict|None]=mapped_column(JSON)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
