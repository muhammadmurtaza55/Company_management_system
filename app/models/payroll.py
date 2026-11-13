"""
Payroll Model Module.

Tracks employee monthly compensation disbursements, bonuses, deductions, and salary history.
Enforces Decimal precision for all financial operations.
Formula: Net Salary = Basic Salary + Bonus - Deductions
"""

from calendar import month_name
from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Payroll(db.Model):
    """Monthly salary payment and payroll ledger record."""
    __tablename__ = "payrolls"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month = db.Column(db.Integer, nullable=False)  # 1-12
    year = db.Column(db.Integer, nullable=False)   # e.g. 2026

    # Financial breakdown (Strict Decimal / Numeric(12, 2))
    base_salary = db.Column(db.Numeric(12, 2), nullable=False)
    bonus = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    bonus_description = db.Column(db.String(255), nullable=True)
    deductions = db.Column(db.Numeric(12, 2), default=0.00, nullable=False)
    deduction_description = db.Column(db.String(255), nullable=True)
    net_salary = db.Column(db.Numeric(12, 2), nullable=False)

    # Disbursement tracking
    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(50), default="Bank Transfer", nullable=False)
    reference_no = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default="paid", nullable=False)  # paid, pending, processing
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    employee = db.relationship("Employee", back_populates="payrolls")

    __table_args__ = (
        db.UniqueConstraint("employee_id", "month", "year", name="uq_employee_payroll_month_year"),
    )

    @property
    def month_str(self) -> str:
        """Returns the full English name of the payroll month."""
        try:
            return month_name[int(self.month)]
        except (IndexError, TypeError, ValueError):
            return str(self.month)

    @property
    def pay_period(self) -> str:
        """Formatted pay period string (e.g. 'November 2026')."""
        return f"{self.month_str} {self.year}"

    @property
    def gross_earnings(self) -> Decimal:
        """Gross earnings before deductions: Base Salary + Bonus."""
        base = Decimal(str(self.base_salary or 0))
        bon = Decimal(str(self.bonus or 0))
        return base + bon

    @classmethod
    def compute_net(cls, base: Decimal | float | str, bonus: Decimal | float | str = 0, deductions: Decimal | float | str = 0) -> Decimal:
        """
        Pure business rule calculation for net salary:
        Net Salary = Basic Salary + Bonus - Deductions
        """
        b = Decimal(str(base or 0))
        bn = Decimal(str(bonus or 0))
        d = Decimal(str(deductions or 0))
        return (b + bn - d).quantize(Decimal("0.01"))

    def recalculate_net(self) -> Decimal:
        """Recalculates and sets net_salary attribute using Decimal precision."""
        self.net_salary = self.compute_net(self.base_salary, self.bonus, self.deductions)
        return self.net_salary

    def __repr__(self) -> str:
        return f"<Payroll Emp #{self.employee_id} {self.month}/{self.year}: ${self.net_salary}>"
