"""
Task Blueprint Package.

Provides company-wide and departmental task workflow, task assignment,
deadline management, status progression, and employee task portals.
"""

from flask import Blueprint

task_bp = Blueprint("task", __name__)

from app.blueprints.task import routes  # noqa: E402, F401

