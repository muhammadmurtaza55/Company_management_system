"""
Main Blueprint Routes.

Handles landing page, system diagnostics, and PostgreSQL connection testing.
"""

from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
import time
import re
from flask import render_template, current_app, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import text
from app.blueprints.main import main_bp
from app.extensions import db
from app.models.employee import Employee
from app.models.department import Department
from app.models.attendance import Attendance
from app.models.task import Task
from app.models.payroll import Payroll
from app.models.leave_request import LeaveRequest


def get_masked_db_uri() -> str:
    """Returns the database URI with password masked for safe display."""
    if not current_app.config.get("POSTGRES_IS_CONFIGURED", False):
        return "Not configured (Pending .env configuration)"
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    # Mask password pattern ://username:password@
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:********@", uri)


def check_postgres_connection():
    """
    Diagnoses the PostgreSQL database connection status.
    Returns a dictionary of connection health metrics and diagnostic information.
    """
    is_configured = current_app.config.get("POSTGRES_IS_CONFIGURED", False)
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")

    if not is_configured:
        return {
            "configured": False,
            "connected": False,
            "status": "NOT_CONFIGURED",
            "message": "PostgreSQL database connection is not configured in .env file.",
            "masked_uri": "Pending .env setup",
            "error": "Missing DATABASE_URL or DB_* environment variables.",
            "instructions": [
                "1. Copy .env.example to .env: copy .env.example .env",
                "2. Set DATABASE_URL to your PostgreSQL connection string, e.g.:",
                "   DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/company_management_db",
                "3. Ensure your PostgreSQL service is running and the database exists.",
                "4. Restart the Flask server and refresh this page.",
            ],
            "version": None,
            "database_name": None,
            "tables": [],
            "latency_ms": None,
        }

    # Ensure URI is PostgreSQL
    if not (uri.startswith("postgresql://") or uri.startswith("postgresql+")):
        return {
            "configured": True,
            "connected": False,
            "status": "INVALID_DRIVER",
            "message": "Only PostgreSQL is permitted. SQLite or MySQL configurations are rejected.",
            "masked_uri": get_masked_db_uri(),
            "error": "Configured database is not PostgreSQL.",
            "instructions": ["Configure a PostgreSQL connection string in .env"],
            "version": None,
            "database_name": None,
            "tables": [],
            "latency_ms": None,
        }

    start_time = time.perf_counter()
    try:
        # Test connection and fetch PostgreSQL metadata
        with db.engine.connect() as conn:
            # Query server version
            version_result = conn.execute(text("SELECT version();")).scalar()
            
            # Query current database name
            current_db = conn.execute(text("SELECT current_database();")).scalar()
            
            # Query existing tables in public schema
            tables_query = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name;"
                )
            ).fetchall()
            tables = [row[0] for row in tables_query]

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "configured": True,
            "connected": True,
            "status": "SUCCESS",
            "message": f"Successfully connected to PostgreSQL database '{current_db}'!",
            "masked_uri": get_masked_db_uri(),
            "version": version_result,
            "database_name": current_db,
            "tables": tables,
            "latency_ms": latency_ms,
            "error": None,
            "instructions": None,
        }

    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        error_msg = str(exc)

        # Categorize common PostgreSQL connection issues
        friendly_hint = "Ensure PostgreSQL is running and credentials in .env are correct."
        if "password authentication failed" in error_msg.lower():
            friendly_hint = "Authentication failed: Check your database username and password in .env."
        elif "connection refused" in error_msg.lower() or "could not connect" in error_msg.lower():
            friendly_hint = "Connection refused: Ensure PostgreSQL server is running and listening on the specified host & port."
        elif "does not exist" in error_msg.lower():
            friendly_hint = "Database does not exist: Run 'createdb <dbname>' or CREATE DATABASE <dbname> in PostgreSQL."

        return {
            "configured": True,
            "connected": False,
            "status": "CONNECTION_FAILED",
            "message": "Failed to connect to PostgreSQL database.",
            "masked_uri": get_masked_db_uri(),
            "error": error_msg,
            "hint": friendly_hint,
            "instructions": [
                "1. Verify your PostgreSQL server is active.",
                "2. Check host, port, user, and password in .env.",
                "3. Verify that the target database exists.",
                "4. Check for firewall or network restrictions if using a remote PostgreSQL host.",
            ],
            "version": None,
            "database_name": None,
            "tables": [],
            "latency_ms": latency_ms,
        }


@main_bp.route("/")
def index():
    """Application home page with smart role-based dashboard redirection."""
    if current_user.is_authenticated and not request.args.get("welcome"):
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        elif current_user.is_manager:
            return redirect(url_for("main.manager_dashboard"))
        elif current_user.is_employee:
            return redirect(url_for("main.employee_dashboard"))

    # Check whether PostgreSQL credentials have been configured in .env
    db_configured = current_app.config.get("POSTGRES_IS_CONFIGURED", False)
    return render_template(
        "main/index.html",
        db_configured=db_configured,
    )


@main_bp.route("/manager/dashboard")
@login_required
def manager_dashboard():
    """Dedicated Manager Operations Dashboard scoped to assigned department."""
    emp = getattr(current_user, "employee", None)
    dept_id = emp.department_id if emp else None
    dept = Department.query.get(dept_id) if dept_id else None

    today = date.today()
    curr_month = today.month
    curr_year = today.year

    # Scoped department staff
    dept_staff = Employee.query.filter_by(department_id=dept_id, status="active").all() if dept_id else []
    dept_staff_ids = [e.id for e in dept_staff]

    # Department Attendance today
    today_attendances = {
        a.employee_id: a
        for a in Attendance.query.filter(
            Attendance.employee_id.in_(dept_staff_ids), Attendance.date == today
        ).all()
    } if dept_staff_ids else {}

    present_today = sum(1 for a in today_attendances.values() if a.status in ("present", "late", "half_day"))
    late_today = sum(1 for a in today_attendances.values() if a.status == "late" or a.is_late)
    on_leave_today = sum(1 for a in today_attendances.values() if a.status == "on_leave")
    pending_today = len(dept_staff) - len(today_attendances)

    # Department pending leave requests
    pending_leaves = (
        LeaveRequest.query.join(Employee)
        .filter(Employee.department_id == dept_id, LeaveRequest.status == "pending")
        .order_by(LeaveRequest.created_at.asc())
        .limit(5)
        .all()
    ) if dept_id else []

    # Department active tasks
    dept_tasks = (
        Task.query.join(Employee, Task.assigned_to_id == Employee.id)
        .filter(Employee.department_id == dept_id)
        .all()
    ) if dept_id else []

    pending_tasks = sum(1 for t in dept_tasks if t.status == "pending")
    in_progress_tasks = sum(1 for t in dept_tasks if t.status == "in_progress")
    completed_tasks = sum(1 for t in dept_tasks if t.status == "completed")
    overdue_tasks = sum(1 for t in dept_tasks if t.is_overdue)

    # Department monthly payroll outlay
    dept_payroll = (
        Payroll.query.join(Employee)
        .filter(Employee.department_id == dept_id, Payroll.month == curr_month, Payroll.year == curr_year)
        .all()
    ) if dept_id else []
    total_dept_payroll = sum((p.net_salary for p in dept_payroll), Decimal("0.00"))

    return render_template(
        "main/manager_dashboard.html",
        emp=emp,
        dept=dept,
        dept_staff=dept_staff,
        present_today=present_today,
        late_today=late_today,
        on_leave_today=on_leave_today,
        pending_today=pending_today,
        pending_leaves=pending_leaves,
        total_tasks=len(dept_tasks),
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        overdue_tasks=overdue_tasks,
        total_dept_payroll=total_dept_payroll,
        recent_tasks=dept_tasks[:6],
    )


@main_bp.route("/employee/dashboard")
@login_required
def employee_dashboard():
    """Dedicated Employee Portal with punch clock, tasks, leave, and salary overview."""
    emp = getattr(current_user, "employee", None)
    if not emp:
        flash("No active employee profile linked to your user account.", "warning")
        return redirect(url_for("main.index", welcome=1))

    today = date.today()

    # Attendance today
    today_attendance = Attendance.query.filter_by(employee_id=emp.id, date=today).first()

    # Monthly attendance summary
    first_of_month = today.replace(day=1)
    month_attendances = Attendance.query.filter(
        Attendance.employee_id == emp.id,
        Attendance.date >= first_of_month,
        Attendance.date <= today,
    ).all()
    days_present = sum(1 for a in month_attendances if a.status in ("present", "late", "half_day"))
    days_late = sum(1 for a in month_attendances if a.status == "late" or a.is_late)

    # Assigned tasks
    assigned_tasks = (
        Task.query.filter_by(assigned_to_id=emp.id)
        .order_by(Task.due_date.asc().nullslast(), Task.id.desc())
        .all()
    )
    pending_tasks = [t for t in assigned_tasks if t.status == "pending"]
    in_progress_tasks = [t for t in assigned_tasks if t.status == "in_progress"]
    completed_tasks = [t for t in assigned_tasks if t.status == "completed"]

    # Leave requests
    my_leaves = (
        LeaveRequest.query.filter_by(employee_id=emp.id)
        .order_by(LeaveRequest.created_at.desc())
        .limit(5)
        .all()
    )

    # Latest payroll slip
    latest_payroll = (
        Payroll.query.filter_by(employee_id=emp.id)
        .order_by(Payroll.year.desc(), Payroll.month.desc())
        .first()
    )

    return render_template(
        "main/employee_dashboard.html",
        emp=emp,
        today=today,
        today_attendance=today_attendance,
        days_present=days_present,
        days_late=days_late,
        assigned_tasks=assigned_tasks[:6],
        pending_count=len(pending_tasks),
        in_progress_count=len(in_progress_tasks),
        completed_count=len(completed_tasks),
        my_leaves=my_leaves,
        latest_payroll=latest_payroll,
    )


@main_bp.route("/db-test")
def db_test():
    """Interactive database diagnostics and connection test page."""
    diagnostics = check_postgres_connection()
    return render_template("main/db_test.html", diagnostics=diagnostics)


@main_bp.route("/about")
def about():
    """System information and architecture overview."""
    return render_template("main/about.html")
