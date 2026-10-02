from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from .records import uid


def now():
    return datetime.now(timezone.utc)


class SelectedHome(Base):
    __tablename__ = "selected_homes"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    housing_id: Mapped[str] = mapped_column(ForeignKey("housing.id"), nullable=False)


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    __table_args__ = (UniqueConstraint("workspace_id", "version", name="uq_plan_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    tasks: Mapped[list] = mapped_column(JSON)
    budget_concerns: Mapped[list] = mapped_column(JSON)
    assumptions: Mapped[list] = mapped_column(JSON)
    missing_information: Mapped[list] = mapped_column(JSON)
    citations: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PlanProposal(Base):
    __tablename__ = "plan_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    base_version: Mapped[int] = mapped_column(Integer)
    context_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    candidate: Mapped[dict] = mapped_column(JSON)
    changes: Mapped[dict] = mapped_column(JSON)
    applied_version: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TaskCompletion(Base):
    __tablename__ = "task_completions"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    completed: Mapped[bool] = mapped_column(default=False)
