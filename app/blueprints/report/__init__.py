"""
Reports Blueprint Package.

Unified reporting engine providing:
- Employee workforce analytics
- Department hierarchy and financial allocations
- Attendance punctuality & lost hours tracking
- Payroll disbursements & salary records in PKR
- Leave utilization analytics
- Task delivery & overdue performance reports
- CSV export & printable PDF report formats
"""

from flask import Blueprint

report_bp = Blueprint("report", __name__)

from app.blueprints.report import routes  # noqa: E402, F401

