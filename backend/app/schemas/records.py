from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


Money = Decimal | None


class ProfileInput(BaseModel):
    destination_city: str = Field(min_length=1, max_length=120)
    workplace_area: str | None = None
    moving_date: date | None = None
    monthly_limit: Money = Field(default=None, ge=0, decimal_places=2)
    upfront_limit: Money = Field(default=None, ge=0, decimal_places=2)
    household_size: int = Field(ge=1, le=30)
    housing_preferences: str | None = None
    commute_preferences: str | None = None


class ProfileOut(ProfileInput):
    model_config = ConfigDict(from_attributes=True)
    id: str


class HousingInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    locality: str = Field(min_length=1, max_length=120)
    rent: Money = Field(default=None, ge=0, decimal_places=2)
    maintenance: Money = Field(default=None, ge=0, decimal_places=2)
    deposit: Money = Field(default=None, ge=0, decimal_places=2)
    furnishing: str | None = None
    notes: str | None = None
    commute_minutes: int | None = Field(default=None, ge=0)
    listing_link: HttpUrl | None = None


class HousingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    locality: str
    rent: Money
    maintenance: Money
    deposit: Money
    furnishing: str | None
    notes: str | None
    commute_minutes: int | None
    listing_link: str | None
    source: Literal["user-entered", "synthetic demo"]


class BudgetInput(BaseModel):
    rent: Money = Field(default=None, ge=0, decimal_places=2)
    maintenance: Money = Field(default=None, ge=0, decimal_places=2)
    utilities: Money = Field(default=None, ge=0, decimal_places=2)
    food: Money = Field(default=None, ge=0, decimal_places=2)
    transport: Money = Field(default=None, ge=0, decimal_places=2)
    miscellaneous: Money = Field(default=None, ge=0, decimal_places=2)
    deposit: Money = Field(default=None, ge=0, decimal_places=2)
    moving_costs: Money = Field(default=None, ge=0, decimal_places=2)
    setup_costs: Money = Field(default=None, ge=0, decimal_places=2)


class BudgetOut(BudgetInput):
    monthly_total: Money
    upfront_nonrefundable: Money
    upfront_refundable: Money
    upfront_total: Money


def total(values: list[Money]) -> Money:
    return sum(values, Decimal("0.00")) if all(value is not None for value in values) else None


def budget_out(value: BudgetInput) -> BudgetOut:
    monthly = total([value.rent, value.maintenance, value.utilities, value.food, value.transport, value.miscellaneous])
    nonrefundable = total([value.moving_costs, value.setup_costs])
    upfront = total([value.deposit, value.moving_costs, value.setup_costs])
    return BudgetOut(**value.model_dump(), monthly_total=monthly, upfront_nonrefundable=nonrefundable,
                     upfront_refundable=value.deposit, upfront_total=upfront)
