"""
Employee Blueprint Routes.

Implements the complete Employee Management Module:
- Directory view with search, department & job title filters, and pagination.
- Role-based scoping: Admin (all), Manager (assigned department only), Employee (own profile only).
- Employee creation, updating, and confirmed deletion (Admin-only).
- Individual detailed profile views with attendance, task, and payroll history.
"""

from datetime import datetime, timezone, date
from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app.blueprints.employee import employee_bp
from app.blueprints.employee.forms import (
    EmployeeCreateForm,
    EmployeeEditForm,
    EmployeeSearchFilterForm,
)
from app.extensions import db
from app.models.employee import Employee
from app.models.department import Department
from app.models.user import User
from app.models.attendance import Attendance
from app.models.task import Task
from app.models.payroll import Payroll
from app.utils.decorators import admin_required


def _check_employee_view_permission(employee: Employee) -> None:
    """
    Enforces role-based view permissions:
    - Admin: can view any employee.
    - Manager: can only view employees in their assigned department.
    - Employee: can only view their own profile.
    Aborts with HTTP 403 Forbidden if unauthorized.
    """
    if current_user.is_admin:
        return

    if current_user.is_manager:
        mgr_profile = getattr(current_user, "employee", None)
        if not mgr_profile or not mgr_profile.department_id:
            abort(403, description="Access denied. You are not assigned to manage any department.")
        if employee.department_id != mgr_profile.department_id:
            abort(403, description="Access denied. You may only view employees within your assigned department.")
        return

    if current_user.is_employee:
        emp_profile = getattr(current_user, "employee", None)
        if not emp_profile or emp_profile.id != employee.id:
            abort(403, description="Access denied. Employees may only view their own profile.")
        return

    abort(403, description="Unauthorized role.")


@employee_bp.route("", methods=["GET"], strict_slashes=False)
@employee_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """
    Lists company employees with search, department filter, job title filter, and pagination.
    - Admin: sees all employees across all departments.
    - Manager: automatically scoped to their assigned department only.
    - Employee: blocked (HTTP 403). Regular employees should view their own profile.
    """
    if current_user.is_employee:
        # Prompt rule: Employee can view their own profile only.
        abort(403, description="Access denied. Regular employees may only view their own profile.")

    mgr_dept = None
    if current_user.is_manager:
        mgr_profile = getattr(current_user, "employee", None)
        if not mgr_profile or not mgr_profile.department_id:
            # Manager has no department assigned
            return render_template(
                "employee/index.html",
                employees=[],
                pagination=None,
                filter_form=EmployeeSearchFilterForm(),
                manager_department=None,
                manager_unassigned=True,
                active_filters={},
            )
        mgr_dept = Department.query.get(mgr_profile.department_id)

    # Initialize search & filter form
    filter_form = EmployeeSearchFilterForm(request.args)
    dept_choices = [(0, "All Departments")] + [
        (d.id, d.name) for d in Department.query.order_by(Department.name.asc()).all()
    ]
    filter_form.department_id.choices = dept_choices

    # Build query
    query = Employee.query

    # Scoping for manager
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_profile.department_id)

    # Search filter (name, employee ID, email)
    search_q = request.args.get("q", "").strip()
    if search_q:
        q_wildcard = f"%{search_q}%"
        query = query.filter(
            or_(
                Employee.first_name.ilike(q_wildcard),
                Employee.last_name.ilike(q_wildcard),
                func.concat(Employee.first_name, " ", Employee.last_name).ilike(q_wildcard),
                Employee.employee_id.ilike(q_wildcard),
                Employee.email.ilike(q_wildcard),
            )
        )

    # Department filter (Admin only, as Manager is pre-scoped)
    dept_id = request.args.get("department_id", type=int)
    if current_user.is_admin and dept_id and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    # Job title filter
    job_title = request.args.get("job_title", "").strip()
    if job_title:
        query = query.filter(Employee.job_title.ilike(f"%{job_title}%"))

    # Employment status filter
    status = request.args.get("status", "").strip()
    if status in ("active", "on_leave", "terminated"):
        query = query.filter(Employee.status == status)

    # Order and paginate
    page = request.args.get("page", 1, type=int)
    per_page = 10
    pagination = query.order_by(Employee.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    active_filters = {
        "q": search_q,
        "department_id": dept_id or 0,
        "job_title": job_title,
        "status": status,
    }

    return render_template(
        "employee/index.html",
        employees=pagination.items,
        pagination=pagination,
        filter_form=filter_form,
        manager_department=mgr_dept,
        manager_unassigned=False,
        active_filters=active_filters,
    )


@employee_bp.route("/profile", strict_slashes=False)
@login_required
def self_profile():
    """Direct route for any logged-in user to view their own linked employee profile."""
    emp_profile = getattr(current_user, "employee", None)
    if not emp_profile:
        flash("You do not currently have an employee profile linked to your user account.", "warning")
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("main.index"))

    return redirect(url_for("employee.detail", id=emp_profile.id))


@employee_bp.route("/<int:id>", strict_slashes=False)
@login_required
def detail(id: int):
    """
    Displays full profile for an employee, including contact info,
    department details, attendance record, assigned tasks, and payroll history.
    """
    employee = Employee.query.get_or_404(id)
    _check_employee_view_permission(employee)

    # Attendance logs (recent 10)
    recent_attendances = (
        Attendance.query.filter_by(employee_id=employee.id)
        .order_by(Attendance.date.desc(), Attendance.id.desc())
        .limit(10)
        .all()
    )

    # Tasks
    active_tasks = (
        Task.query.filter(
            Task.assigned_to_id == employee.id,
            Task.status.in_(["pending", "in_progress"]),
        )
        .order_by(Task.due_date.asc().nullslast())
        .all()
    )
    completed_tasks = (
        Task.query.filter(
            Task.assigned_to_id == employee.id,
            Task.status == "completed",
        )
        .order_by(Task.completed_at.desc().nullslast())
        .limit(5)
        .all()
    )

    # Payroll records (recent 6)
    payrolls = (
        Payroll.query.filter_by(employee_id=employee.id)
        .order_by(Payroll.year.desc(), Payroll.month.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "employee/detail.html",
        employee=employee,
        attendances=recent_attendances,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        payrolls=payrolls,
    )


@employee_bp.route("/create", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def create():
    """
    Registers a new employee (Admin-only).
    Validates unique Employee ID, unique Email, required fields, and department assignment.
    """
    form = EmployeeCreateForm()

    # Populate department choices
    departments = Department.query.order_by(Department.name.asc()).all()
    form.department_id.choices = [(0, "No Department Assigned")] + [
        (d.id, f"{d.name} ({d.code})") for d in departments
    ]

    # Populate unlinked user choices
    unlinked_users = (
        User.query.filter(User.employee == None)  # noqa: E711
        .order_by(User.username.asc())
        .all()
    )
    form.user_id.choices = [(0, "No User Account Linked")] + [
        (u.id, f"{u.username} ({u.email}) [{u.role.title()}]") for u in unlinked_users
    ]

    if form.validate_on_submit():
        dept_id = form.department_id.data if form.department_id.data != 0 else None
        user_link_id = form.user_id.data if form.user_id.data != 0 else None

        employee = Employee(
            employee_id=form.employee_id.data.strip().upper(),
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip() if form.phone.data else None,
            address=form.address.data.strip() if form.address.data else None,
            job_title=form.job_title.data.strip(),
            department_id=dept_id,
            user_id=user_link_id,
            hire_date=form.hire_date.data,
            salary=form.salary.data,
            status=form.status.data,
        )

        db.session.add(employee)
        db.session.commit()

        flash(
            f"Employee '{employee.full_name}' ({employee.employee_id}) created successfully!",
            "success",
        )
        return redirect(url_for("employee.detail", id=employee.id))

    # Pre-generate suggested employee ID on GET
    if request.method == "GET" and not form.employee_id.data:
        next_count = Employee.query.count() + 1
        form.employee_id.data = f"EMP-{next_count:04d}"

    return render_template("employee/form.html", form=form, is_edit=False, employee=None)


@employee_bp.route("/<int:id>/edit", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def edit(id: int):
    """
    Updates an existing employee's information (Admin-only).
    Enforces uniqueness checks excluding the record itself.
    """
    employee = Employee.query.get_or_404(id)
    form = EmployeeEditForm(original_id=employee.id)

    # Populate department choices
    departments = Department.query.order_by(Department.name.asc()).all()
    form.department_id.choices = [(0, "No Department Assigned")] + [
        (d.id, f"{d.name} ({d.code})") for d in departments
    ]

    # Populate available user accounts (unlinked users + the user currently linked to this employee)
    available_users = (
        User.query.filter(
            or_(User.employee == None, User.id == employee.user_id)  # noqa: E711
        )
        .order_by(User.username.asc())
        .all()
    )
    form.user_id.choices = [(0, "No User Account Linked")] + [
        (u.id, f"{u.username} ({u.email}) [{u.role.title()}]") for u in available_users
    ]

    if form.validate_on_submit():
        dept_id = form.department_id.data if form.department_id.data != 0 else None
        user_link_id = form.user_id.data if form.user_id.data != 0 else None

        employee.employee_id = form.employee_id.data.strip().upper()
        employee.first_name = form.first_name.data.strip()
        employee.last_name = form.last_name.data.strip()
        employee.email = form.email.data.strip().lower()
        employee.phone = form.phone.data.strip() if form.phone.data else None
        employee.address = form.address.data.strip() if form.address.data else None
        employee.job_title = form.job_title.data.strip()
        employee.department_id = dept_id
        employee.user_id = user_link_id
        employee.hire_date = form.hire_date.data
        employee.salary = form.salary.data
        employee.status = form.status.data

        db.session.commit()
        flash(f"Employee profile for '{employee.full_name}' updated successfully!", "success")
        return redirect(url_for("employee.detail", id=employee.id))

    # Pre-populate form fields on GET
    if request.method == "GET":
        form.employee_id.data = employee.employee_id
        form.first_name.data = employee.first_name
        form.last_name.data = employee.last_name
        form.email.data = employee.email
        form.phone.data = employee.phone
        form.address.data = employee.address
        form.job_title.data = employee.job_title
        form.department_id.data = employee.department_id or 0
        form.user_id.data = employee.user_id or 0
        form.hire_date.data = employee.hire_date
        form.salary.data = employee.salary
        form.status.data = employee.status

    return render_template(
        "employee/form.html",
        form=form,
        is_edit=True,
        employee=employee,
    )


@employee_bp.route("/<int:id>/delete", methods=["POST"], strict_slashes=False)
@login_required
@admin_required
def delete(id: int):
    """
    Deletes an employee profile with confirmation (Admin-only).
    Safely unlinks user login and tasks before removal.
    """
    employee = Employee.query.get_or_404(id)
    emp_name = employee.full_name
    emp_code = employee.employee_id

    # Unassign corporate tasks so they are not deleted
    Task.query.filter_by(assigned_to_id=employee.id).update(
        {"assigned_to_id": None}, synchronize_session=False
    )

    db.session.delete(employee)
    db.session.commit()

    flash(f"Employee '{emp_name}' ({emp_code}) has been deleted successfully.", "warning")
    return redirect(url_for("employee.index"))

