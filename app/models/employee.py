"""
Employee Model Module.

Represents employee profiles, linked optionally to a User login account and a Department.
"""

from datetime import datetime, timezone
import uuid
from app.extensions import db


class Employee(db.Model):
    """Employee entity representing company staff members."""
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(32), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)

    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)
    address = db.Column(db.Text, nullable=True)
    job_title = db.Column(db.String(100), nullable=False)
    hire_date = db.Column(db.Date, nullable=True)
    salary = db.Column(db.Numeric(12, 2), nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)  # active, on_leave, terminated

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = db.relationship("User", back_populates="employee")
    department = db.relationship("Department", back_populates="employees", foreign_keys=[department_id])
    attendances = db.relationship("Attendance", back_populates="employee", cascade="all, delete-orphan", lazy="dynamic")
    tasks = db.relationship("Task", back_populates="assignee", lazy="dynamic")
    payrolls = db.relationship("Payroll", back_populates="employee", cascade="all, delete-orphan", lazy="dynamic")
    leave_requests = db.relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan", lazy="dynamic")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.employee_id:
            self.employee_id = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        if not self.email:
            fn = (self.first_name or "emp").strip().lower().replace(" ", "")
            ln = (self.last_name or "user").strip().lower().replace(" ", "")
            self.email = f"{fn}.{ln}.{uuid.uuid4().hex[:4]}@company.local"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def joining_date(self):
        """Alias for hire_date."""
        return self.hire_date

    @joining_date.setter
    def joining_date(self, value):
        self.hire_date = value

    @property
    def base_salary(self):
        """Alias for salary."""
        return self.salary

    @base_salary.setter
    def base_salary(self, value):
        self.salary = value

    def to_dict(self) -> dict:
        """Serializes employee profile for API and views."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone or "",
            "address": self.address or "",
            "job_title": self.job_title,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "joining_date": self.hire_date.isoformat() if self.hire_date else None,
            "base_salary": float(self.salary) if self.salary is not None else None,
            "status": self.status,
            "user_id": self.user_id,
            "has_login": bool(self.user_id),
        }

    def __repr__(self) -> str:
        return f"<Employee {self.employee_id} {self.full_name} - {self.job_title}>"
