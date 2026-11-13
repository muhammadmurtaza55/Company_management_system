"""
Department Model Module.

Represents organizational units within the company (e.g. Engineering, Sales, HR),
with manager assignment, workforce metrics, and salary aggregation.
"""

from datetime import datetime, timezone
from app.extensions import db


class Department(db.Model):
    """Department model for organizational categorization and workforce management."""
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    manager_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 1-to-1 / M-to-1 Relationship to Department Manager
    manager = db.relationship(
        "Employee",
        foreign_keys=[manager_id],
        backref=db.backref("managed_department", uselist=False),
    )

    # 1-to-Many Relationship with Department Employees
    employees = db.relationship(
        "Employee",
        foreign_keys="Employee.department_id",
        back_populates="department",
        lazy="select",
    )

    @property
    def total_employees(self) -> int:
        return len(self.employees)

    @property
    def active_employees_count(self) -> int:
        return sum(1 for e in self.employees if e.status == "active")

    @property
    def on_leave_count(self) -> int:
        return sum(1 for e in self.employees if e.status == "on_leave")

    @property
    def terminated_count(self) -> int:
        return sum(1 for e in self.employees if e.status == "terminated")

    @property
    def total_salary_expense(self) -> float:
        return sum(float(e.salary or 0) for e in self.employees if e.status == "active")

    @property
    def average_salary(self) -> float:
        active = [float(e.salary or 0) for e in self.employees if e.status == "active" and e.salary]
        return (sum(active) / len(active)) if active else 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "manager_id": self.manager_id,
            "manager_name": self.manager.full_name if self.manager else None,
            "total_employees": self.total_employees,
            "active_employees": self.active_employees_count,
            "on_leave_employees": self.on_leave_count,
            "terminated_employees": self.terminated_count,
            "total_salary_expense": self.total_salary_expense,
            "average_salary": round(self.average_salary, 2),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Department {self.code} - {self.name}>"
