"""
Admin Blueprint Routes.

Implements the Executive Admin Dashboard with real-time PostgreSQL metrics,
interactive charts, and functional module management views.
"""

from datetime import datetime, timezone, date, timedelta
from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app.blueprints.admin import admin_bp
from app.blueprints.admin.forms import (
    DepartmentForm,
    EmployeeForm,
    TaskForm,
    AttendanceForm,
    PayrollForm,
)
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.task import Task
from app.models.payroll import Payroll
from app.utils.decorators import admin_required


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    """
    Renders the executive Admin Dashboard with real-time statistics,
    charts, and recent activity from PostgreSQL.
    """
    today = datetime.now(timezone.utc).date()
    current_month = today.month
    current_year = today.year

    # -------------------------------------------------------------------------
    # 1-7 Core Dashboard Statistics (Strictly PostgreSQL)
    # -------------------------------------------------------------------------
    total_employees = Employee.query.count()
    total_departments = Department.query.count()

    # Today's Attendance
    today_present = Attendance.query.filter(
        Attendance.date == today, Attendance.status == "present"
    ).count()
    today_absent = Attendance.query.filter(
        Attendance.date == today, Attendance.status == "absent"
    ).count()

    # Monthly Salary Expenses
    actual_payroll = db.session.query(
        func.coalesce(func.sum(Payroll.net_salary), 0)
    ).filter(Payroll.month == current_month, Payroll.year == current_year).scalar()

    committed_payroll = db.session.query(
        func.coalesce(func.sum(Employee.salary), 0)
    ).filter(Employee.status == "active").scalar()

    # If actual payroll was processed for this month, display it; otherwise show committed active salary
    monthly_salary_expenses = float(actual_payroll if actual_payroll > 0 else committed_payroll)

    # Task Statistics
    pending_tasks = Task.query.filter(
        Task.status.in_(["pending", "in_progress"])
    ).count()
    completed_tasks = Task.query.filter(Task.status == "completed").count()

    # -------------------------------------------------------------------------
    # Recent Activities
    # -------------------------------------------------------------------------
    recent_employees = (
        Employee.query.order_by(Employee.created_at.desc()).limit(5).all()
    )
    recent_attendance = (
        Attendance.query.order_by(Attendance.date.desc(), Attendance.created_at.desc())
        .limit(5)
        .all()
    )
    recent_tasks = Task.query.order_by(Task.created_at.desc()).limit(5).all()

    # -------------------------------------------------------------------------
    # Chart 1: Department-wise Employee Distribution
    # -------------------------------------------------------------------------
    dept_query = (
        db.session.query(Department.name, func.count(Employee.id))
        .outerjoin(Employee, Employee.department_id == Department.id)
        .group_by(Department.id, Department.name)
        .order_by(func.count(Employee.id).desc())
        .all()
    )
    dept_labels = [row[0] for row in dept_query] if dept_query else []
    dept_counts = [row[1] for row in dept_query] if dept_query else []

    # -------------------------------------------------------------------------
    # Chart 2: 7-Day Attendance Trend
    # -------------------------------------------------------------------------
    seven_days_ago = today - timedelta(days=6)
    dates_list = [seven_days_ago + timedelta(days=i) for i in range(7)]
    attendance_labels = [d.strftime("%b %d") for d in dates_list]
    present_trend = []
    absent_trend = []

    for d in dates_list:
        p_c = Attendance.query.filter(Attendance.date == d, Attendance.status == "present").count()
        a_c = Attendance.query.filter(Attendance.date == d, Attendance.status == "absent").count()
        present_trend.append(p_c)
        absent_trend.append(a_c)

    # -------------------------------------------------------------------------
    # Chart 3: Monthly Salary Expense Trend (Past 6 Months)
    # -------------------------------------------------------------------------
    salary_labels = []
    salary_data = []
    for i in range(5, -1, -1):
        # Sample month calculation
        m_date = today.replace(day=1) - timedelta(days=i * 30)
        salary_labels.append(m_date.strftime("%b %Y"))

        m_sum = db.session.query(
            func.coalesce(func.sum(Payroll.net_salary), 0)
        ).filter(Payroll.month == m_date.month, Payroll.year == m_date.year).scalar()

        if m_sum == 0 and m_date.month == current_month and m_date.year == current_year:
            m_sum = committed_payroll

        salary_data.append(float(m_sum))

    return render_template(
        "admin/dashboard.html",
        stats={
            "total_employees": total_employees,
            "total_departments": total_departments,
            "today_present": today_present,
            "today_absent": today_absent,
            "monthly_salary_expenses": monthly_salary_expenses,
            "pending_tasks": pending_tasks,
            "completed_tasks": completed_tasks,
        },
        recent_employees=recent_employees,
        recent_attendance=recent_attendance,
        recent_tasks=recent_tasks,
        charts={
            "dept_labels": dept_labels,
            "dept_counts": dept_counts,
            "attendance_labels": attendance_labels,
            "present_trend": present_trend,
            "absent_trend": absent_trend,
            "salary_labels": salary_labels,
            "salary_data": salary_data,
        },
        today=today,
    )


# -----------------------------------------------------------------------------
# Functional Module Views
# -----------------------------------------------------------------------------
@admin_bp.route("/employees", methods=["GET", "POST"])
@login_required
@admin_required
def employees():
    """Lists and creates company employees."""
    form = EmployeeForm()
    # Populate departments dropdown dynamically
    form.department_id.choices = [
        (0, "No Department Assigned")
    ] + [(d.id, f"{d.name} ({d.code})") for d in Department.query.order_by(Department.name.asc()).all()]

    if form.validate_on_submit():
        dept_id = form.department_id.data if form.department_id.data != 0 else None
        emp = Employee(
            first_name=form.first_name.data.strip(),
            last_name=form.last_name.data.strip(),
            job_title=form.job_title.data.strip(),
            department_id=dept_id,
            salary=form.salary.data,
            hire_date=form.hire_date.data,
            status=form.status.data,
        )
        db.session.add(emp)
        db.session.commit()
        flash(f"Employee '{emp.full_name}' added successfully!", "success")
        return redirect(url_for("admin.employees"))

    employee_list = Employee.query.order_by(Employee.id.desc()).all()
    return render_template("admin/employees.html", employees=employee_list, form=form)


@admin_bp.route("/departments", methods=["GET", "POST"])
@login_required
@admin_required
def departments():
    """Lists and creates corporate departments."""
    form = DepartmentForm()

    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        existing = Department.query.filter(
            (func.lower(Department.name) == func.lower(form.name.data.strip()))
            | (Department.code == code)
        ).first()
        if existing:
            flash(f"A department with this name or code '{code}' already exists.", "danger")
        else:
            dept = Department(
                name=form.name.data.strip(),
                code=code,
                description=form.description.data.strip() if form.description.data else None,
            )
            db.session.add(dept)
            db.session.commit()
            flash(f"Department '{dept.name}' ({dept.code}) created successfully!", "success")
            return redirect(url_for("admin.departments"))

    department_list = Department.query.order_by(Department.name.asc()).all()
    return render_template("admin/departments.html", departments=department_list, form=form)


@admin_bp.route("/attendance", methods=["GET", "POST"])
@login_required
@admin_required
def attendance():
    """Lists and records employee attendance entries."""
    form = AttendanceForm()
    # Populate employees dropdown dynamically
    employees_query = Employee.query.order_by(Employee.first_name.asc()).all()
    form.employee_id.choices = [(e.id, f"{e.full_name} (#{e.id})") for e in employees_query]

    if form.validate_on_submit():
        emp_id = form.employee_id.data
        att_date = form.date.data
        existing = Attendance.query.filter_by(employee_id=emp_id, date=att_date).first()

        if existing:
            existing.status = form.status.data
            existing.notes = form.notes.data
            flash("Attendance record updated successfully!", "info")
        else:
            new_att = Attendance(
                employee_id=emp_id,
                date=att_date,
                status=form.status.data,
                notes=form.notes.data,
            )
            db.session.add(new_att)
            flash("Attendance logged successfully!", "success")

        db.session.commit()
        return redirect(url_for("admin.attendance"))

    attendance_list = (
        Attendance.query.order_by(Attendance.date.desc(), Attendance.id.desc()).all()
    )
    return render_template(
        "admin/attendance.html",
        attendance_records=attendance_list,
        form=form,
        has_employees=bool(employees_query),
    )


@admin_bp.route("/tasks", methods=["GET", "POST"])
@login_required
@admin_required
def tasks():
    """Lists, filters, and creates corporate tasks."""
    form = TaskForm()
    employees_query = Employee.query.order_by(Employee.first_name.asc()).all()
    form.assigned_to_id.choices = [(0, "Unassigned")] + [
        (e.id, f"{e.full_name} ({e.job_title})") for e in employees_query
    ]

    if form.validate_on_submit():
        assignee_id = (
            form.assigned_to_id.data if form.assigned_to_id.data != 0 else None
        )
        task = Task(
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            assigned_to_id=assignee_id,
            created_by_id=current_user.id,
            priority=form.priority.data,
            status=form.status.data,
            due_date=form.due_date.data,
        )
        if form.status.data == "completed":
            task.completed_at = datetime.now(timezone.utc)

        db.session.add(task)
        db.session.commit()
        flash(f"Task '{task.title}' created successfully!", "success")
        return redirect(url_for("admin.tasks"))

    tasks_list = Task.query.order_by(Task.created_at.desc()).all()
    return render_template("admin/tasks.html", tasks=tasks_list, form=form)


@admin_bp.route("/tasks/<int:task_id>/toggle-complete", methods=["POST"])
@login_required
@admin_required
def toggle_task_complete(task_id: int):
    """Toggles task status between pending and completed."""
    task = Task.query.get_or_404(task_id)
    if task.status == "completed":
        task.status = "pending"
        task.completed_at = None
        flash(f"Task '{task.title}' marked as Pending.", "info")
    else:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
        flash(f"Task '{task.title}' marked as Completed!", "success")

    db.session.commit()
    return redirect(url_for("admin.tasks"))


@admin_bp.route("/payroll", methods=["GET", "POST"])
@login_required
@admin_required
def payroll():
    """Lists and logs payroll disbursements."""
    form = PayrollForm()
    employees_query = Employee.query.order_by(Employee.first_name.asc()).all()
    form.employee_id.choices = [(e.id, f"{e.full_name} (${e.salary or 0.00}/mo)") for e in employees_query]

    if form.validate_on_submit():
        emp_id = form.employee_id.data
        m = form.month.data
        y = form.year.data
        base = form.base_salary.data
        bonus = form.bonus.data or 0.0
        ded = form.deductions.data or 0.0
        net = base + bonus - ded

        existing = Payroll.query.filter_by(employee_id=emp_id, month=m, year=y).first()
        if existing:
            existing.base_salary = base
            existing.bonus = bonus
            existing.deductions = ded
            existing.net_salary = net
            existing.status = form.status.data
            existing.payment_date = form.payment_date.data
            flash(f"Payroll record updated for month {m}/{y}.", "info")
        else:
            rec = Payroll(
                employee_id=emp_id,
                month=m,
                year=y,
                base_salary=base,
                bonus=bonus,
                deductions=ded,
                net_salary=net,
                status=form.status.data,
                payment_date=form.payment_date.data,
            )
            db.session.add(rec)
            flash("Payroll disbursement recorded successfully!", "success")

        db.session.commit()
        return redirect(url_for("admin.payroll"))

    payroll_records = (
        Payroll.query.order_by(Payroll.year.desc(), Payroll.month.desc(), Payroll.id.desc()).all()
    )
    return render_template(
        "admin/payroll.html",
        payrolls=payroll_records,
        form=form,
        has_employees=bool(employees_query),
    )

