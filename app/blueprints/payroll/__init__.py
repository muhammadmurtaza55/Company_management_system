"""
Payroll Blueprint Package.

Handles employee salary management, compensation structures, bonuses, deductions,
net salary calculations, monthly payroll generation, salary slips, and reporting.
"""

from flask import Blueprint

payroll_bp = Blueprint("payroll", __name__)

from app.blueprints.payroll import routes  # noqa: E402, F401

