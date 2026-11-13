"""
Reports Blueprint Routes.

Implements the Enterprise Reporting Module:
- Employee reports (headcount, status, compensation).
- Department reports (manager, staffing, financial outlay).
- Attendance reports (attendance rate, late incidents, absence).
- Payroll reports (basic salary, bonus, deductions, net pay in PKR).
- Leave reports (leave types, approved/rejected, calendar duration).
- Task reports (completion performance, priority distributions, overdue tracking).
- Date filters on all analytics.
- CSV and printable PDF report exports.
"""

from calendar import month_name
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
import io
from flask import (
    render_template,
    request,
    abort,
    Response,
)
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app.blueprints.report import report_bp
from app.models.employee import Employee
from app.models.department import Department
from app.models.attendance import Attendance
from app.models.payroll import Payroll
from app.models.leave_request import LeaveRequest
from app.models.task import Task


def _get_manager_dept_id():
    """Returns department ID managed by current user, if manager."""
    if current_user.is_manager:
        emp = getattr(current_user, "employee", None)
        return emp.department_id if emp else None
    return None


def _check_report_access():
    """Restricts reports to Admins and Managers. Employees receive 403."""
    if current_user.is_employee:
        abort(403, description="Access denied. Company reporting is restricted to management personnel.")


# -----------------------------------------------------------------------------
# 1. Reports Hub Directory
# -----------------------------------------------------------------------------
@report_bp.route("", methods=["GET"], strict_slashes=False)
@report_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """Executive Reports Dashboard linking to all 6 reporting suites."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    # High-level summary metrics
    emp_q = Employee.query
    task_q = Task.query
    dept_q = Department.query

    if current_user.is_manager:
        emp_q = emp_q.filter(Employee.department_id == mgr_dept_id)
        task_q = task_q.join(Employee, Task.assigned_to_id == Employee.id).filter(Employee.department_id == mgr_dept_id)
        dept_q = dept_q.filter(Department.id == mgr_dept_id)

    stats = {
        "total_employees": emp_q.count(),
        "active_employees": emp_q.filter(Employee.status == "active").count(),
        "total_departments": dept_q.count(),
        "total_tasks": task_q.count(),
        "completed_tasks": task_q.filter(Task.status == "completed").count(),
    }

    return render_template("report/index.html", stats=stats)


# -----------------------------------------------------------------------------
# 2. Employee Workforce Report
# -----------------------------------------------------------------------------
@report_bp.route("/employees", methods=["GET"], strict_slashes=False)
@login_required
def employee_report():
    """Workforce demographics, job titles, department distributions, and statuses."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Employee.query
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    status_f = request.args.get("status", "").strip()
    if status_f in ("active", "on_leave", "terminated"):
        query = query.filter(Employee.status == status_f)

    employees = query.order_by(Employee.last_name.asc()).all()
    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []

    total_payroll_cost = sum((e.salary for e in employees if e.salary), Decimal("0.00"))

    return render_template(
        "report/employee_report.html",
        employees=employees,
        departments=departments,
        total_payroll_cost=total_payroll_cost,
        selected_dept_id=dept_id or 0,
        selected_status=status_f,
    )


@report_bp.route("/employees/export", methods=["GET"], strict_slashes=False)
@login_required
def export_employees_csv():
    """Exports employee workforce report to CSV."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Employee.query
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    status_f = request.args.get("status", "").strip()
    if status_f:
        query = query.filter(Employee.status == status_f)

    employees = query.order_by(Employee.last_name.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee ID",
        "Full Name",
        "Email",
        "Phone",
        "Job Title",
        "Department",
        "Joining Date",
        "Base Salary (PKR)",
        "Status",
    ])

    for e in employees:
        writer.writerow([
            e.employee_id,
            e.full_name,
            e.email,
            e.phone or "",
            e.job_title,
            e.department.name if e.department else "Unassigned",
            e.hire_date.isoformat() if e.hire_date else "",
            f"{e.salary:.2f}" if e.salary else "0.00",
            e.status.title(),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=employees_report_{date.today().isoformat()}.csv"},
    )


# -----------------------------------------------------------------------------
# 3. Department Analytics Report
# -----------------------------------------------------------------------------
@report_bp.route("/departments", methods=["GET"], strict_slashes=False)
@login_required
def department_report():
    """Department staffing, manager assignments, and salary budget distribution."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Department.query
    if current_user.is_manager:
        query = query.filter(Department.id == mgr_dept_id)

    departments = query.order_by(Department.name.asc()).all()

    dept_stats = []
    total_company_staff = 0
    total_company_salary = Decimal("0.00")

    for d in departments:
        staff = d.employees.all()
        salaries = [e.salary for e in staff if e.salary is not None]
        tot_sal = sum(salaries, Decimal("0.00"))
        avg_sal = (tot_sal / len(salaries)) if salaries else Decimal("0.00")

        total_company_staff += len(staff)
        total_company_salary += tot_sal

        dept_stats.append({
            "department": d,
            "manager_name": d.manager.full_name if d.manager else "None Assigned",
            "staff_count": len(staff),
            "active_count": sum(1 for e in staff if e.status == "active"),
            "total_salary": tot_sal,
            "avg_salary": avg_sal,
        })

    return render_template(
        "report/department_report.html",
        dept_stats=dept_stats,
        total_company_staff=total_company_staff,
        total_company_salary=total_company_salary,
    )


@report_bp.route("/departments/export", methods=["GET"], strict_slashes=False)
@login_required
def export_departments_csv():
    """Exports department report to CSV."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Department.query
    if current_user.is_manager:
        query = query.filter(Department.id == mgr_dept_id)

    departments = query.order_by(Department.name.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Department Code",
        "Department Name",
        "Manager Name",
        "Total Staff",
        "Active Staff",
        "Total Monthly Salary (PKR)",
        "Average Salary (PKR)",
    ])

    for d in departments:
        staff = d.employees.all()
        salaries = [e.salary for e in staff if e.salary is not None]
        tot_sal = sum(salaries, Decimal("0.00"))
        avg_sal = (tot_sal / len(salaries)) if salaries else Decimal("0.00")

        writer.writerow([
            d.code,
            d.name,
            d.manager.full_name if d.manager else "Unassigned",
            len(staff),
            sum(1 for e in staff if e.status == "active"),
            f"{tot_sal:.2f}",
            f"{avg_sal:.2f}",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=departments_report_{date.today().isoformat()}.csv"},
    )


# -----------------------------------------------------------------------------
# 4. Attendance Analytics Report
# -----------------------------------------------------------------------------
@report_bp.route("/attendance", methods=["GET"], strict_slashes=False)
@login_required
def attendance_report():
    """Attendance punctuality, late arrivals, and absence tracking."""
    _check_report_access()
    today = date.today()
    from_date_str = request.args.get("from_date", today.replace(day=1).isoformat())
    to_date_str = request.args.get("to_date", today.isoformat())

    try:
        d_from = datetime.strptime(from_date_str, "%Y-%m-%d").date()
    except ValueError:
        d_from = today.replace(day=1)

    try:
        d_to = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except ValueError:
        d_to = today

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Attendance.query.join(Employee).filter(
        Attendance.date >= d_from, Attendance.date <= d_to
    )

    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    status_f = request.args.get("status", "").strip()
    if status_f in ("present", "late", "absent", "on_leave"):
        query = query.filter(Attendance.status == status_f)

    records = query.order_by(Attendance.date.desc(), Employee.last_name.asc()).all()

    counts = {
        "total": len(records),
        "present": sum(1 for r in records if r.status == "present"),
        "late": sum(1 for r in records if r.status == "late" or r.is_late),
        "on_leave": sum(1 for r in records if r.status == "on_leave"),
        "absent": sum(1 for r in records if r.status == "absent"),
    }

    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []

    return render_template(
        "report/attendance_report.html",
        records=records,
        counts=counts,
        from_date=d_from,
        to_date=d_to,
        departments=departments,
        selected_dept_id=dept_id or 0,
        selected_status=status_f,
    )


@report_bp.route("/attendance/export", methods=["GET"], strict_slashes=False)
@login_required
def export_attendance_csv():
    """Exports attendance report to CSV."""
    _check_report_access()
    today = date.today()
    from_date_str = request.args.get("from_date", today.replace(day=1).isoformat())
    to_date_str = request.args.get("to_date", today.isoformat())

    try:
        d_from = datetime.strptime(from_date_str, "%Y-%m-%d").date()
        d_to = datetime.strptime(to_date_str, "%Y-%m-%d").date()
    except ValueError:
        d_from = today.replace(day=1)
        d_to = today

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None
    query = Attendance.query.join(Employee).filter(
        Attendance.date >= d_from, Attendance.date <= d_to
    )

    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    records = query.order_by(Attendance.date.desc(), Employee.last_name.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date",
        "Employee ID",
        "Employee Name",
        "Department",
        "Status",
        "Check-In Time",
        "Check-Out Time",
        "Work Duration",
        "Minutes Late",
        "Notes",
    ])

    for r in records:
        writer.writerow([
            r.date.isoformat(),
            r.employee.employee_id,
            r.employee.full_name,
            r.employee.department.name if r.employee.department else "Unassigned",
            r.status.title(),
            r.check_in.strftime("%I:%M %p") if r.check_in else "",
            r.check_out.strftime("%I:%M %p") if r.check_out else "",
            r.work_duration_formatted,
            r.minutes_late if r.is_late else 0,
            r.notes or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attendance_report_{d_from}_to_{d_to}.csv"},
    )


# -----------------------------------------------------------------------------
# 5. Payroll Disbursement Report (Currency: PKR)
# -----------------------------------------------------------------------------
@report_bp.route("/payroll", methods=["GET"], strict_slashes=False)
@login_required
def payroll_report():
    """Payroll compensation, bonuses, deductions, and net disbursements in PKR."""
    _check_report_access()
    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    dept_id = request.args.get("department_id", type=int)
    status_f = request.args.get("status", "").strip()

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Payroll.query.join(Employee).filter(Payroll.month == month, Payroll.year == year)

    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    if status_f in ("paid", "pending", "processing"):
        query = query.filter(Payroll.status == status_f)

    records = query.order_by(Employee.last_name.asc()).all()

    totals = {
        "basic": sum((r.base_salary for r in records), Decimal("0.00")),
        "bonus": sum((r.bonus for r in records), Decimal("0.00")),
        "deductions": sum((r.deductions for r in records), Decimal("0.00")),
        "net": sum((r.net_salary for r in records), Decimal("0.00")),
    }

    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []

    return render_template(
        "report/payroll_report.html",
        records=records,
        month=month,
        year=year,
        month_name=month_name[month],
        totals=totals,
        departments=departments,
        selected_dept_id=dept_id or 0,
        selected_status=status_f,
    )


@report_bp.route("/payroll/export", methods=["GET"], strict_slashes=False)
@login_required
def export_payroll_csv():
    """Exports payroll report to CSV."""
    _check_report_access()
    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    dept_id = request.args.get("department_id", type=int)
    status_f = request.args.get("status", "").strip()

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Payroll.query.join(Employee).filter(Payroll.month == month, Payroll.year == year)
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)
    if status_f:
        query = query.filter(Payroll.status == status_f)

    records = query.order_by(Employee.last_name.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Employee ID",
        "Employee Name",
        "Department",
        "Month",
        "Year",
        "Basic Salary (PKR)",
        "Bonus (PKR)",
        "Deductions (PKR)",
        "Net Salary (PKR)",
        "Payment Date",
        "Payment Method",
        "Status",
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.employee.employee_id,
            r.employee.full_name,
            r.employee.department.name if r.employee.department else "Unassigned",
            r.month_str,
            r.year,
            f"{r.base_salary:.2f}",
            f"{r.bonus:.2f}",
            f"{r.deductions:.2f}",
            f"{r.net_salary:.2f}",
            r.payment_date.isoformat() if r.payment_date else "",
            r.payment_method,
            r.status.title(),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=payroll_report_{year}_{month:02d}.csv"},
    )


# -----------------------------------------------------------------------------
# 6. Leave Analytics Report
# -----------------------------------------------------------------------------
@report_bp.route("/leaves", methods=["GET"], strict_slashes=False)
@login_required
def leave_report():
    """Leave utilization, pending reviews, and approved time off analysis."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = LeaveRequest.query.join(Employee)
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    status_f = request.args.get("status", "").strip()
    if status_f in ("pending", "approved", "rejected", "cancelled"):
        query = query.filter(LeaveRequest.status == status_f)

    leave_type_f = request.args.get("leave_type", "").strip()
    if leave_type_f:
        query = query.filter(LeaveRequest.leave_type == leave_type_f)

    leaves = query.order_by(LeaveRequest.created_at.desc()).all()

    counts = {
        "total": len(leaves),
        "pending": sum(1 for l in leaves if l.status == "pending"),
        "approved": sum(1 for l in leaves if l.status == "approved"),
        "rejected": sum(1 for l in leaves if l.status == "rejected"),
        "total_days": sum(l.duration_days for l in leaves if l.status == "approved"),
    }

    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []

    return render_template(
        "report/leave_report.html",
        leaves=leaves,
        counts=counts,
        departments=departments,
        selected_dept_id=dept_id or 0,
        selected_status=status_f,
        selected_type=leave_type_f,
    )


@report_bp.route("/leaves/export", methods=["GET"], strict_slashes=False)
@login_required
def export_leaves_csv():
    """Exports leave report to CSV."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = LeaveRequest.query.join(Employee)
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    leaves = query.order_by(LeaveRequest.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Leave ID",
        "Employee ID",
        "Employee Name",
        "Department",
        "Leave Type",
        "Start Date",
        "End Date",
        "Duration (Days)",
        "Status",
        "Reason",
        "Review Notes",
    ])

    for l in leaves:
        writer.writerow([
            l.id,
            l.employee.employee_id,
            l.employee.full_name,
            l.employee.department.name if l.employee.department else "Unassigned",
            l.leave_type.title(),
            l.start_date.isoformat(),
            l.end_date.isoformat(),
            l.duration_days,
            l.status.title(),
            l.reason,
            l.review_notes or "",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leave_report_{date.today().isoformat()}.csv"},
    )


# -----------------------------------------------------------------------------
# 7. Task Execution Performance Report
# -----------------------------------------------------------------------------
@report_bp.route("/tasks", methods=["GET"], strict_slashes=False)
@login_required
def task_report():
    """Task delivery metrics, priority loads, and overdue tracking."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Task.query.outerjoin(Employee, Task.assigned_to_id == Employee.id)
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    status_f = request.args.get("status", "").strip()
    if status_f in Task.STATUSES:
        query = query.filter(Task.status == status_f)

    priority_f = request.args.get("priority", "").strip()
    if priority_f in Task.PRIORITIES:
        query = query.filter(Task.priority == priority_f)

    tasks = query.order_by(Task.due_date.asc().nullslast(), Task.id.desc()).all()

    counts = {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.status == "pending"),
        "in_progress": sum(1 for t in tasks if t.status == "in_progress"),
        "completed": sum(1 for t in tasks if t.status == "completed"),
        "overdue": sum(1 for t in tasks if t.is_overdue),
    }

    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []

    return render_template(
        "report/task_report.html",
        tasks=tasks,
        counts=counts,
        departments=departments,
        selected_dept_id=dept_id or 0,
        selected_status=status_f,
        selected_priority=priority_f,
    )


@report_bp.route("/tasks/export", methods=["GET"], strict_slashes=False)
@login_required
def export_tasks_csv():
    """Exports tasks report to CSV."""
    _check_report_access()
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    query = Task.query.outerjoin(Employee, Task.assigned_to_id == Employee.id)
    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    tasks = query.order_by(Task.due_date.asc().nullslast()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Task ID",
        "Title",
        "Assignee Name",
        "Department",
        "Priority",
        "Status",
        "Due Date",
        "Completed At",
        "Is Overdue",
    ])

    for t in tasks:
        writer.writerow([
            t.id,
            t.title,
            t.assignee.full_name if t.assignee else "Unassigned",
            t.assignee.department.name if t.assignee and t.assignee.department else "Unassigned",
            t.priority.title(),
            t.status.replace("_", " ").title(),
            t.due_date.isoformat() if t.due_date else "",
            t.completed_at.isoformat() if t.completed_at else "",
            "Yes" if t.is_overdue else "No",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=tasks_report_{date.today().isoformat()}.csv"},
    )

