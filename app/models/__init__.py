"""
Models package initialization.

Exports all database models and registers the Flask-Login user loader.
"""

from app.extensions import db, login_manager
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.task import Task
from app.models.payroll import Payroll
from app.models.leave_request import LeaveRequest


@login_manager.user_loader
def load_user(user_id: str):
    """Flask-Login user loader callback."""
    return db.session.get(User, int(user_id))


__all__ = ["User", "Department", "Employee", "Attendance", "Task", "Payroll", "LeaveRequest", "load_user"]

