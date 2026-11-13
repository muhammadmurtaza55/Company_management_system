"""
Department Blueprint Package.

Handles corporate organizational structure, department creation,
editing, manager assignments, employee allocation, and workforce statistics.
"""

from flask import Blueprint

department_bp = Blueprint("department", __name__, url_prefix="/departments")

from app.blueprints.department import routes  # noqa: F401, E402

