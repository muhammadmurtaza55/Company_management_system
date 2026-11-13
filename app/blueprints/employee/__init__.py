"""
Employee Blueprint Package.

Handles employee directory, profiles, CRUD operations, department scoping,
and role-based access control.
"""

from flask import Blueprint

employee_bp = Blueprint("employee", __name__, url_prefix="/employees")

from app.blueprints.employee import routes  # noqa: F401, E402

