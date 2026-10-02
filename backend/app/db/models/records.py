import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


def uid():
    return str(uuid.uuid4())


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("identity_issuer", "identity_subject", name="uq_workspace_identity"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    identity_issuer: Mapped[str | None] = mapped_column(String(255))
    identity_subject: Mapped[str | None] = mapped_column(String(255))


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), unique=True, index=True)
    destination_city: Mapped[str] = mapped_column(String(120))
    workplace_area: Mapped[str | None] = mapped_column(String(120))
    moving_date: Mapped[date | None] = mapped_column(Date)
    monthly_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    upfront_limit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    household_size: Mapped[int] = mapped_column(Integer)
    housing_preferences: Mapped[str | None] = mapped_column(Text)
    commute_preferences: Mapped[str | None] = mapped_column(Text)


class Housing(Base):
    __tablename__ = "housing"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    locality: Mapped[str] = mapped_column(String(120))
    rent: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    maintenance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    deposit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    furnishing: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    commute_minutes: Mapped[int | None] = mapped_column(Integer)
    listing_link: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), default="user-entered")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_budget_workspace"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    rent: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    maintenance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    utilities: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    food: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    transport: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    miscellaneous: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    deposit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    moving_costs: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    setup_costs: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
