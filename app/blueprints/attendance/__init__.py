"""
Attendance Blueprint Package.

Handles employee daily check-in, check-out, late arrival tracking,
attendance history, daily & monthly reports, and leave management workflows.
"""

from flask import Blueprint

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")

from app.blueprints.attendance import routes  # noqa: F401, E402

