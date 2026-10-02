from decimal import Decimal
from app.schemas.records import BudgetInput, budget_out


def test_exact_totals_and_refundable_separation():
    result = budget_out(BudgetInput(rent=Decimal('12000.10'), maintenance=Decimal('1000.20'), utilities=Decimal('500.30'), food=Decimal('3000.40'), transport=Decimal('800.50'), miscellaneous=Decimal('100.60'), deposit=Decimal('25000.00'), moving_costs=Decimal('5000.25'), setup_costs=Decimal('1000.15')))
    assert result.monthly_total == Decimal('17402.10')
    assert result.upfront_nonrefundable == Decimal('6000.40')
    assert result.upfront_refundable == Decimal('25000.00')
    assert result.upfront_total == Decimal('31000.40')


def test_unknown_stays_unknown():
    result = budget_out(BudgetInput(rent=Decimal('10000')))
    assert result.monthly_total is None
    assert result.upfront_total is None
