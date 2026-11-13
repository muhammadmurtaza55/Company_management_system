"""
Department Blueprint Routes.

Implements the complete Department Management Module:
- Department directory with high-level workforce metrics and search.
- Department detailed profile with KPI statistics cards and employee roster.
- Department creation and editing with unique checks and manager assignment.
- Accidental deletion protection: Prevents deleting departments with active staff.
- Staff allocation: Assign and remove employees to/from departments.
"""

from datetime import datetime, timezone
from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app.blueprints.department import department_bp
from app.blueprints.department.forms import (
    DepartmentCreateForm,
    DepartmentEditForm,
    AssignEmployeeForm,
    DepartmentSearchFilterForm,
)
from app.extensions import db
from app.models.department import Department
from app.models.employee import Employee
from app.utils.decorators import admin_required


@department_bp.route("", methods=["GET"], strict_slashes=False)
@department_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """
    Lists corporate departments with search, manager details, and workforce stats.
    Accessible to Admin and Manager accounts.
    """
    search_q = request.args.get("q", "").strip()
    query = Department.query

    if search_q:
        q_wildcard = f"%{search_q}%"
        query = query.outerjoin(Employee, Department.manager_id == Employee.id).filter(
            or_(
                Department.name.ilike(q_wildcard),
                Department.code.ilike(q_wildcard),
                Department.description.ilike(q_wildcard),
                Employee.first_name.ilike(q_wildcard),
                Employee.last_name.ilike(q_wildcard),
            )
        )

    departments_list = query.order_by(Department.name.asc()).all()

    # Aggregate company-wide department statistics
    total_depts = len(departments_list)
    total_workforce = sum(d.total_employees for d in departments_list)
    total_monthly_payroll = sum(d.total_salary_expense for d in departments_list)
    managed_depts = sum(1 for d in departments_list if d.manager_id is not None)

    summary_stats = {
        "total_departments": total_depts,
        "total_workforce": total_workforce,
        "total_payroll": total_monthly_payroll,
        "managed_departments": managed_depts,
        "unmanaged_departments": total_depts - managed_depts,
    }

    filter_form = DepartmentSearchFilterForm(request.args)

    return render_template(
        "department/index.html",
        departments=departments_list,
        summary_stats=summary_stats,
        filter_form=filter_form,
        search_query=search_q,
    )


@department_bp.route("/<int:id>", methods=["GET"], strict_slashes=False)
@login_required
def detail(id: int):
    """
    Displays detailed view of a department:
    - Core info & assigned manager.
    - Workforce breakdown statistics (Active, On Leave, Terminated, Total Payroll, Average Salary).
    - Complete roster of employees assigned to this department.
    - Action forms to assign or remove staff (Admin only).
    """
    dept = Department.query.get_or_404(id)

    # Scoping rule: If current user is a manager, they can view their own department.
    # Regular employees can only view their own department.
    if current_user.is_employee:
        emp_profile = getattr(current_user, "employee", None)
        if not emp_profile or emp_profile.department_id != dept.id:
            abort(403, description="Access denied. You may only view your assigned department.")

    # Employees in this department
    dept_employees = Employee.query.filter_by(department_id=dept.id).order_by(
        Employee.last_name.asc(), Employee.first_name.asc()
    ).all()

    # Prepare employee assignment form for Admin
    assign_form = None
    if current_user.is_admin:
        assign_form = AssignEmployeeForm()
        # Find employees NOT currently in this department
        unassigned_employees = Employee.query.filter(
            or_(Employee.department_id != dept.id, Employee.department_id == None)  # noqa: E711
        ).order_by(Employee.last_name.asc()).all()
        
        assign_form.employee_id.choices = [(0, "Select an employee...")] + [
            (
                e.id,
                f"{e.full_name} ({e.employee_id}) - {e.job_title} "
                f"[{'Current: ' + e.department.name if e.department else 'Unassigned'}]"
            )
            for e in unassigned_employees
        ]

    # Department statistics dictionary
    dept_stats = {
        "total_employees": dept.total_employees,
        "active_employees": dept.active_employees_count,
        "on_leave": dept.on_leave_count,
        "terminated": dept.terminated_count,
        "total_salary_expense": dept.total_salary_expense,
        "average_salary": dept.average_salary,
    }

    return render_template(
        "department/detail.html",
        department=dept,
        employees=dept_employees,
        stats=dept_stats,
        assign_form=assign_form,
    )


@department_bp.route("/create", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def create():
    """
    Creates a new corporate department (Admin-only).
    Validates unique department name and unique code, and assigns a manager.
    """
    form = DepartmentCreateForm()

    # Populate managers dropdown (all active employees)
    candidates = Employee.query.order_by(Employee.last_name.asc()).all()
    form.manager_id.choices = [(0, "No Manager Assigned")] + [
        (e.id, f"{e.full_name} ({e.employee_id}) - {e.job_title}") for e in candidates
    ]

    if form.validate_on_submit():
        mgr_id = form.manager_id.data if form.manager_id.data != 0 else None

        dept = Department(
            name=form.name.data.strip(),
            code=form.code.data.strip().upper(),
            description=form.description.data.strip() if form.description.data else None,
            manager_id=mgr_id,
        )
        db.session.add(dept)
        db.session.flush()

        # If manager selected, ensure their department is set to this department
        if mgr_id:
            manager_emp = Employee.query.get(mgr_id)
            if manager_emp and manager_emp.department_id != dept.id:
                manager_emp.department_id = dept.id

        db.session.commit()
        flash(f"Department '{dept.name}' ({dept.code}) created successfully!", "success")
        return redirect(url_for("department.detail", id=dept.id))

    return render_template("department/form.html", form=form, is_edit=False, department=None)


@department_bp.route("/<int:id>/edit", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def edit(id: int):
    """
    Edits department information and updates manager assignment (Admin-only).
    """
    dept = Department.query.get_or_404(id)
    form = DepartmentEditForm(original_id=dept.id)

    candidates = Employee.query.order_by(Employee.last_name.asc()).all()
    form.manager_id.choices = [(0, "No Manager Assigned")] + [
        (e.id, f"{e.full_name} ({e.employee_id}) - {e.job_title}") for e in candidates
    ]

    if form.validate_on_submit():
        mgr_id = form.manager_id.data if form.manager_id.data != 0 else None

        dept.name = form.name.data.strip()
        dept.code = form.code.data.strip().upper()
        dept.description = form.description.data.strip() if form.description.data else None
        dept.manager_id = mgr_id

        # If manager changed/assigned, ensure that employee belongs to this department
        if mgr_id:
            manager_emp = Employee.query.get(mgr_id)
            if manager_emp and manager_emp.department_id != dept.id:
                manager_emp.department_id = dept.id

        db.session.commit()
        flash(f"Department '{dept.name}' ({dept.code}) updated successfully!", "success")
        return redirect(url_for("department.detail", id=dept.id))

    # Pre-populate on GET
    if request.method == "GET":
        form.name.data = dept.name
        form.code.data = dept.code
        form.description.data = dept.description
        form.manager_id.data = dept.manager_id or 0

    return render_template("department/form.html", form=form, is_edit=True, department=dept)


@department_bp.route("/<int:id>/delete", methods=["POST"], strict_slashes=False)
@login_required
@admin_required
def delete(id: int):
    """
    Deletes a department (Admin-only).
    STRICT SAFETY RULE: Prevents deletion if any employees are currently assigned to the department.
    """
    dept = Department.query.get_or_404(id)
    dept_name = dept.name
    dept_code = dept.code

    # Check for assigned employees
    assigned_count = Employee.query.filter_by(department_id=dept.id).count()
    if assigned_count > 0:
        flash(
            f"Cannot delete department '{dept_name}' ({dept_code}) because {assigned_count} "
            f"employee(s) are currently assigned to it. Please reassign or remove all employees "
            f"before deleting this department.",
            "danger",
        )
        return redirect(url_for("department.detail", id=dept.id))

    db.session.delete(dept)
    db.session.commit()

    flash(f"Department '{dept_name}' ({dept_code}) deleted successfully.", "warning")
    return redirect(url_for("department.index"))


@department_bp.route("/<int:id>/assign-employee", methods=["POST"], strict_slashes=False)
@login_required
@admin_required
def assign_employee(id: int):
    """
    Assigns an existing employee to this department (Admin-only).
    """
    dept = Department.query.get_or_404(id)
    emp_id = request.form.get("employee_id", type=int)

    if not emp_id or emp_id <= 0:
        flash("Please select a valid employee to assign.", "warning")
        return redirect(url_for("department.detail", id=dept.id))

    employee = Employee.query.get_or_404(emp_id)
    previous_dept_name = employee.department.name if employee.department else None

    employee.department_id = dept.id
    db.session.commit()

    if previous_dept_name and previous_dept_name != dept.name:
        flash(
            f"Employee '{employee.full_name}' was transferred from {previous_dept_name} to {dept.name}.",
            "success",
        )
    else:
        flash(f"Employee '{employee.full_name}' assigned to {dept.name} successfully!", "success")

    return redirect(url_for("department.detail", id=dept.id))


@department_bp.route("/<int:id>/remove-employee/<int:employee_id>", methods=["POST"], strict_slashes=False)
@login_required
@admin_required
def remove_employee(id: int, employee_id: int):
    """
    Unassigns an employee from this department (Admin-only).
    If the removed employee was the department manager, also unsets manager_id.
    """
    dept = Department.query.get_or_404(id)
    employee = Employee.query.get_or_404(employee_id)

    if employee.department_id != dept.id:
        flash(f"Employee '{employee.full_name}' is not assigned to {dept.name}.", "warning")
        return redirect(url_for("department.detail", id=dept.id))

    employee.department_id = None

    # If this employee was the department's manager, clear the manager assignment
    if dept.manager_id == employee.id:
        dept.manager_id = None

    db.session.commit()
    flash(f"Employee '{employee.full_name}' was removed from {dept.name}.", "info")
    return redirect(url_for("department.detail", id=dept.id))

