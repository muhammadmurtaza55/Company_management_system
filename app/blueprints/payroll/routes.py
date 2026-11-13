"""
Payroll Blueprint Routes.

Implements the Salary and Payroll Management Module:
1. Set/update employee structural basic salary.
2. Add bonuses and deductions with descriptive reasons.
3. Calculate Net Salary using strict Decimal precision: Net Salary = Basic Salary + Bonus - Deductions.
4. Generate individual and batch monthly salary records.
5. View salary history with role-based scoping (Admin: all, Manager: department, Employee: self).
6. Search salary records by employee name or ID.
7. Generate professional, print-ready salary slips (Payslips).
8. Export payroll reports to CSV format.
"""

from calendar import month_name
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import io
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    abort,
    Response,
    jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app.blueprints.payroll import payroll_bp
from app.blueprints.payroll.forms import (
    PayrollRecordForm,
    BatchPayrollGenerateForm,
    UpdateBaseSalaryForm,
)
from app.extensions import db
from app.models.payroll import Payroll
from app.models.employee import Employee
from app.models.department import Department
from app.utils.decorators import admin_required


def _get_manager_dept_id():
    """Returns department ID managed by the current user, or None."""
    if current_user.is_manager:
        emp = getattr(current_user, "employee", None)
        return emp.department_id if emp else None
    return None


def _check_payroll_access_permission(payroll: Payroll):
    """
    Enforces privacy access control for viewing salary records and payslips:
    - Admin: Can access any record.
    - Manager: Can only access records for employees in their department.
    - Employee: Can ONLY access their own records.
    Aborts with HTTP 403 Forbidden on violation.
    """
    if current_user.is_admin:
        return

    emp = getattr(current_user, "employee", None)

    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        if not mgr_dept_id:
            abort(403, description="Access denied. You are not assigned to manage any department.")
        if payroll.employee.department_id != mgr_dept_id:
            abort(403, description="Access denied. You may only view salary records within your department.")
        return

    if current_user.is_employee:
        if not emp or payroll.employee_id != emp.id:
            abort(403, description="Access denied. You may only view your own salary records.")
        return

    abort(403, description="Unauthorized access to salary records.")


# -----------------------------------------------------------------------------
# 1. Main Payroll Dashboard & Overview
# -----------------------------------------------------------------------------
@payroll_bp.route("", methods=["GET"], strict_slashes=False)
@payroll_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """
    Main Payroll Hub:
    - Admin: Company payroll KPIs (monthly disbursements, average salary, pending items, recent pay records).
    - Manager: Department payroll totals and staff pay records.
    - Employee: Personal salary overview, latest pay receipt, and direct link to payslips.
    """
    emp = getattr(current_user, "employee", None)
    today = date.today()
    curr_month = today.month
    curr_year = today.year

    # 1. Employee Self-Service View
    if current_user.is_employee:
        if not emp:
            flash("No active employee profile linked to your user account.", "warning")
            return redirect(url_for("main.index"))

        # Fetch employee's personal salary history
        personal_payrolls = (
            Payroll.query.filter_by(employee_id=emp.id)
            .order_by(Payroll.year.desc(), Payroll.month.desc())
            .all()
        )

        latest_payroll = personal_payrolls[0] if personal_payrolls else None
        ytd_earnings = sum(
            (p.net_salary for p in personal_payrolls if p.year == curr_year and p.status == "paid"),
            Decimal("0.00"),
        )
        total_bonus_ytd = sum(
            (p.bonus for p in personal_payrolls if p.year == curr_year and p.status == "paid"),
            Decimal("0.00"),
        )

        return render_template(
            "payroll/index.html",
            emp=emp,
            latest_payroll=latest_payroll,
            personal_payrolls=personal_payrolls[:10],
            ytd_earnings=ytd_earnings,
            total_bonus_ytd=total_bonus_ytd,
            curr_month=curr_month,
            curr_year=curr_year,
        )

    # 2. Admin & Manager Management View
    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    # Base query for employees and payrolls
    emp_query = Employee.query.filter(Employee.status == "active")
    pay_query = Payroll.query.join(Employee)

    if current_user.is_manager:
        emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)
        pay_query = pay_query.filter(Employee.department_id == mgr_dept_id)

    total_active_staff = emp_query.count()

    # Current month stats
    curr_month_records = pay_query.filter(
        Payroll.month == curr_month, Payroll.year == curr_year
    ).all()

    total_disbursed_month = sum(
        (p.net_salary for p in curr_month_records if p.status == "paid"),
        Decimal("0.00"),
    )
    total_pending_month = sum(
        (p.net_salary for p in curr_month_records if p.status in ("pending", "processing")),
        Decimal("0.00"),
    )
    total_bonuses_month = sum(
        (p.bonus for p in curr_month_records),
        Decimal("0.00"),
    )
    total_deductions_month = sum(
        (p.deductions for p in curr_month_records),
        Decimal("0.00"),
    )

    # Calculate average base salary of active staff
    active_salaries = [e.salary for e in emp_query.all() if e.salary is not None]
    avg_salary = (
        (sum(active_salaries, Decimal("0.00")) / len(active_salaries))
        if active_salaries
        else Decimal("0.00")
    )

    # Recent payroll logs
    recent_payrolls = (
        pay_query.order_by(Payroll.year.desc(), Payroll.month.desc(), Payroll.id.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "payroll/index.html",
        emp=emp,
        curr_month=curr_month,
        curr_year=curr_year,
        curr_month_name=month_name[curr_month],
        total_active_staff=total_active_staff,
        total_disbursed_month=total_disbursed_month,
        total_pending_month=total_pending_month,
        total_bonuses_month=total_bonuses_month,
        total_deductions_month=total_deductions_month,
        avg_salary=avg_salary,
        recent_payrolls=recent_payrolls,
        processed_count_month=len(curr_month_records),
    )


# -----------------------------------------------------------------------------
# 2. View Salary History & Search by Employee
# -----------------------------------------------------------------------------
@payroll_bp.route("/history", methods=["GET"], strict_slashes=False)
@login_required
def history():
    """
    Searchable salary history table with pagination:
    - Scoped to user's permissions (Admin: all, Manager: department, Employee: self).
    - Search by employee name or Employee ID.
    - Filter by department, month, year, status.
    """
    emp = getattr(current_user, "employee", None)
    query = Payroll.query.join(Employee)

    # Scoping
    if current_user.is_employee:
        if not emp:
            flash("No active employee profile found.", "warning")
            return redirect(url_for("main.index"))
        query = query.filter(Payroll.employee_id == emp.id)
    elif current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        query = query.filter(Employee.department_id == mgr_dept_id)

    # Filters
    search_q = request.args.get("search", "").strip()
    if search_q and not current_user.is_employee:
        query = query.filter(
            or_(
                Employee.first_name.ilike(f"%{search_q}%"),
                Employee.last_name.ilike(f"%{search_q}%"),
                Employee.employee_id.ilike(f"%{search_q}%"),
                Payroll.reference_no.ilike(f"%{search_q}%"),
            )
        )

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    m = request.args.get("month", type=int)
    if m and 1 <= m <= 12:
        query = query.filter(Payroll.month == m)

    y = request.args.get("year", type=int)
    if y and y > 2000:
        query = query.filter(Payroll.year == y)

    st = request.args.get("status", "").strip()
    if st in ("paid", "pending", "processing"):
        query = query.filter(Payroll.status == st)

    # Pagination
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(
        Payroll.year.desc(), Payroll.month.desc(), Payroll.id.desc()
    ).paginate(page=page, per_page=15, error_out=False)

    departments = (
        Department.query.order_by(Department.name.asc()).all()
        if current_user.is_admin
        else []
    )

    return render_template(
        "payroll/history.html",
        records=pagination.items,
        pagination=pagination,
        departments=departments,
        active_filters={
            "search": search_q,
            "department_id": dept_id or 0,
            "month": m or 0,
            "year": y or 0,
            "status": st,
        },
    )


# -----------------------------------------------------------------------------
# 3. Create Individual Payroll Record (Admin Only)
# -----------------------------------------------------------------------------
@payroll_bp.route("/create", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def create():
    """
    Creates an individual monthly salary record for an employee.
    Calculates net salary: Net Salary = Basic Salary + Bonus - Deductions.
    Prevents duplicate entries for the same employee in the same month/year.
    """
    form = PayrollRecordForm()
    employees = Employee.query.order_by(Employee.last_name.asc()).all()
    form.employee_id.choices = [(0, "Select Employee...")] + [
        (e.id, f"{e.full_name} ({e.employee_id}) - ${float(e.salary or 0):,.2f}")
        for e in employees
    ]

    # Pre-select employee if passed in query string
    emp_preselect_id = request.args.get("employee_id", type=int)
    if request.method == "GET" and emp_preselect_id:
        target_emp = Employee.query.get(emp_preselect_id)
        if target_emp:
            form.employee_id.data = target_emp.id
            form.base_salary.data = target_emp.salary or Decimal("0.00")

    if form.validate_on_submit():
        if form.employee_id.data == 0:
            flash("Please choose a valid employee.", "danger")
            return render_template("payroll/create_form.html", form=form)

        emp_id = form.employee_id.data
        month = form.month.data
        year = form.year.data

        # Duplicate check
        existing = Payroll.query.filter_by(
            employee_id=emp_id, month=month, year=year
        ).first()
        if existing:
            flash(
                f"A payroll record for this employee already exists for {month_name[month]} {year}. "
                f"You can edit or delete record #{existing.id}.",
                "danger",
            )
            return render_template("payroll/create_form.html", form=form)

        base_sal = Decimal(str(form.base_salary.data))
        bonus_val = Decimal(str(form.bonus.data or 0))
        deductions_val = Decimal(str(form.deductions.data or 0))

        # Formula: Net Salary = Basic Salary + Bonus - Deductions
        net_sal = Payroll.compute_net(base_sal, bonus_val, deductions_val)

        new_payroll = Payroll(
            employee_id=emp_id,
            month=month,
            year=year,
            base_salary=base_sal,
            bonus=bonus_val,
            bonus_description=form.bonus_description.data.strip() if form.bonus_description.data else None,
            deductions=deductions_val,
            deduction_description=form.deduction_description.data.strip() if form.deduction_description.data else None,
            net_salary=net_sal,
            payment_date=form.payment_date.data,
            payment_method=form.payment_method.data,
            reference_no=form.reference_no.data.strip() if form.reference_no.data else None,
            status=form.status.data,
            notes=form.notes.data.strip() if form.notes.data else None,
        )

        db.session.add(new_payroll)
        db.session.commit()

        flash(
            f"Payroll record created successfully for {new_payroll.employee.full_name} "
            f"({new_payroll.pay_period})! Net Salary: ${net_sal:,.2f}",
            "success",
        )
        return redirect(url_for("payroll.salary_slip", id=new_payroll.id))

    return render_template("payroll/create_form.html", form=form)


# -----------------------------------------------------------------------------
# 4. Edit Existing Payroll Record (Admin Only)
# -----------------------------------------------------------------------------
@payroll_bp.route("/<int:id>/edit", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def edit(id: int):
    """Edits an existing payroll record and recalculates net salary."""
    payroll = Payroll.query.get_or_404(id)
    form = PayrollRecordForm(obj=payroll)

    employees = Employee.query.order_by(Employee.last_name.asc()).all()
    form.employee_id.choices = [
        (e.id, f"{e.full_name} ({e.employee_id})") for e in employees
    ]

    if form.validate_on_submit():
        # Check duplicate if employee/month/year changed
        if (
            form.employee_id.data != payroll.employee_id
            or form.month.data != payroll.month
            or form.year.data != payroll.year
        ):
            duplicate = Payroll.query.filter(
                Payroll.employee_id == form.employee_id.data,
                Payroll.month == form.month.data,
                Payroll.year == form.year.data,
                Payroll.id != payroll.id,
            ).first()
            if duplicate:
                flash(
                    f"A payroll record already exists for {month_name[form.month.data]} {form.year.data}.",
                    "danger",
                )
                return render_template("payroll/create_form.html", form=form, payroll=payroll, is_edit=True)

        payroll.employee_id = form.employee_id.data
        payroll.month = form.month.data
        payroll.year = form.year.data
        payroll.base_salary = Decimal(str(form.base_salary.data))
        payroll.bonus = Decimal(str(form.bonus.data or 0))
        payroll.bonus_description = form.bonus_description.data.strip() if form.bonus_description.data else None
        payroll.deductions = Decimal(str(form.deductions.data or 0))
        payroll.deduction_description = form.deduction_description.data.strip() if form.deduction_description.data else None

        # Re-apply formula: Net = Basic + Bonus - Deductions
        payroll.recalculate_net()

        payroll.payment_date = form.payment_date.data
        payroll.payment_method = form.payment_method.data
        payroll.reference_no = form.reference_no.data.strip() if form.reference_no.data else None
        payroll.status = form.status.data
        payroll.notes = form.notes.data.strip() if form.notes.data else None

        db.session.commit()
        flash(f"Payroll record #{payroll.id} updated successfully! Net Salary: ${payroll.net_salary:,.2f}", "success")
        return redirect(url_for("payroll.salary_slip", id=payroll.id))

    return render_template("payroll/create_form.html", form=form, payroll=payroll, is_edit=True)


# -----------------------------------------------------------------------------
# 5. Delete Payroll Record (Admin Only)
# -----------------------------------------------------------------------------
@payroll_bp.route("/<int:id>/delete", methods=["POST"], strict_slashes=False)
@login_required
@admin_required
def delete(id: int):
    """Deletes a payroll disbursement record."""
    payroll = Payroll.query.get_or_404(id)
    emp_name = payroll.employee.full_name
    period = payroll.pay_period

    db.session.delete(payroll)
    db.session.commit()

    flash(f"Payroll record #{id} for {emp_name} ({period}) deleted successfully.", "info")
    return redirect(url_for("payroll.history"))


# -----------------------------------------------------------------------------
# 6. Batch Generate Monthly Payroll (Admin Only)
# -----------------------------------------------------------------------------
@payroll_bp.route("/batch", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def batch_generate():
    """
    Batch provisions monthly payroll records for all active employees.
    Automatically assigns each employee's basic salary (`Employee.salary`),
    initializes bonus/deductions to 0.00, and calculates net salary.
    """
    form = BatchPayrollGenerateForm()

    departments = Department.query.order_by(Department.name.asc()).all()
    form.department_id.choices = [(0, "All Active Departments")] + [
        (d.id, d.name) for d in departments
    ]

    if form.validate_on_submit():
        month = form.month.data
        year = form.year.data
        dept_id = form.department_id.data
        pay_date = form.payment_date.data
        pay_method = form.payment_method.data
        status = form.status.data
        overwrite = form.overwrite_existing.data

        emp_query = Employee.query.filter(Employee.status == "active")
        if dept_id and dept_id > 0:
            emp_query = emp_query.filter(Employee.department_id == dept_id)

        active_employees = emp_query.all()
        if not active_employees:
            flash("No active employees found matching the criteria.", "warning")
            return render_template("payroll/batch_generate.html", form=form)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for emp in active_employees:
            existing = Payroll.query.filter_by(
                employee_id=emp.id, month=month, year=year
            ).first()

            base_sal = Decimal(str(emp.salary or 0))

            if existing:
                if overwrite:
                    existing.base_salary = base_sal
                    existing.payment_date = pay_date
                    existing.payment_method = pay_method
                    existing.status = status
                    existing.recalculate_net()
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                net_sal = Payroll.compute_net(base_sal, 0, 0)
                new_record = Payroll(
                    employee_id=emp.id,
                    month=month,
                    year=year,
                    base_salary=base_sal,
                    bonus=Decimal("0.00"),
                    deductions=Decimal("0.00"),
                    net_salary=net_sal,
                    payment_date=pay_date,
                    payment_method=pay_method,
                    status=status,
                    notes="Batch generated run",
                )
                db.session.add(new_record)
                created_count += 1

        db.session.commit()

        msg = (
            f"Batch payroll run for {month_name[month]} {year} completed! "
            f"Created: {created_count}, Updated: {updated_count}, Skipped (Already existed): {skipped_count}."
        )
        flash(msg, "success")
        return redirect(url_for("payroll.history", month=month, year=year))

    return render_template("payroll/batch_generate.html", form=form)


# -----------------------------------------------------------------------------
# 7. Set / Update Employee Basic Salary (Admin Only)
# -----------------------------------------------------------------------------
@payroll_bp.route("/salary/update", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def update_salary():
    """
    Interface for setting or adjusting an employee's structural basic salary.
    Directly updates `Employee.salary`.
    """
    form = UpdateBaseSalaryForm()
    employees = Employee.query.order_by(Employee.last_name.asc()).all()
    form.employee_id.choices = [(0, "Select Employee...")] + [
        (e.id, f"{e.full_name} ({e.employee_id}) - Current: ${float(e.salary or 0):,.2f}")
        for e in employees
    ]

    emp_id_param = request.args.get("employee_id", type=int)
    if request.method == "GET" and emp_id_param:
        emp = Employee.query.get(emp_id_param)
        if emp:
            form.employee_id.data = emp.id
            form.new_salary.data = emp.salary

    if form.validate_on_submit():
        if form.employee_id.data == 0:
            flash("Please choose an employee.", "danger")
            return render_template("payroll/update_salary.html", form=form)

        target_emp = Employee.query.get_or_404(form.employee_id.data)
        old_salary = target_emp.salary or Decimal("0.00")
        new_salary = Decimal(str(form.new_salary.data))

        target_emp.salary = new_salary
        target_emp.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash(
            f"Basic salary for {target_emp.full_name} updated from ${old_salary:,.2f} "
            f"to ${new_salary:,.2f}!",
            "success",
        )
        return redirect(url_for("employee.detail", id=target_emp.id))

    return render_template("payroll/update_salary.html", form=form)


# -----------------------------------------------------------------------------
# 8. Generate Salary Slip (Payslip)
# -----------------------------------------------------------------------------
@payroll_bp.route("/slip/<int:id>", methods=["GET"], strict_slashes=False)
@login_required
def salary_slip(id: int):
    """
    Generates a formal, printable Salary Slip.
    Enforces strict privacy:
    - Admin: Can view any payslip.
    - Manager: Can view payslips for employees in their department only.
    - Employee: Can view their OWN payslip only.
    """
    payroll = Payroll.query.get_or_404(id)
    _check_payroll_access_permission(payroll)

    return render_template("payroll/salary_slip.html", payroll=payroll)


# -----------------------------------------------------------------------------
# 9. Export Payroll Reports (CSV)
# -----------------------------------------------------------------------------
@payroll_bp.route("/export/csv", methods=["GET"], strict_slashes=False)
@login_required
def export_csv():
    """
    Exports payroll disbursements to CSV format.
    Enforces role-based scoping (Admin: all, Manager: department).
    Employees cannot export company payroll reports.
    """
    if current_user.is_employee:
        abort(403, description="Employees are not authorized to export payroll reports.")

    query = Payroll.query.join(Employee)

    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        query = query.filter(Employee.department_id == mgr_dept_id)

    # Apply filters
    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    m = request.args.get("month", type=int)
    if m and 1 <= m <= 12:
        query = query.filter(Payroll.month == m)

    y = request.args.get("year", type=int)
    if y and y > 2000:
        query = query.filter(Payroll.year == y)

    st = request.args.get("status", "").strip()
    if st in ("paid", "pending", "processing"):
        query = query.filter(Payroll.status == st)

    records = query.order_by(Payroll.year.desc(), Payroll.month.desc(), Employee.last_name.asc()).all()

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header Row
    writer.writerow([
        "Payroll ID",
        "Employee ID",
        "Employee Name",
        "Department",
        "Job Title",
        "Pay Month",
        "Pay Year",
        "Basic Salary ($)",
        "Bonus ($)",
        "Bonus Description",
        "Deductions ($)",
        "Deduction Description",
        "Net Salary ($)",
        "Payment Date",
        "Payment Method",
        "Reference No",
        "Status",
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.employee.employee_id,
            r.employee.full_name,
            r.employee.department.name if r.employee.department else "Unassigned",
            r.employee.job_title,
            r.month_str,
            r.year,
            f"{r.base_salary:.2f}",
            f"{r.bonus:.2f}",
            r.bonus_description or "",
            f"{r.deductions:.2f}",
            r.deduction_description or "",
            f"{r.net_salary:.2f}",
            r.payment_date.isoformat() if r.payment_date else "",
            r.payment_method,
            r.reference_no or "",
            r.status.title(),
        ])

    csv_data = output.getvalue()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"payroll_export_{timestamp}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# -----------------------------------------------------------------------------
# 10. Helper JSON API for Dynamic Form Autocomplete
# -----------------------------------------------------------------------------
@payroll_bp.route("/api/employee-salary/<int:employee_id>", methods=["GET"], strict_slashes=False)
@login_required
@admin_required
def get_employee_salary(employee_id: int):
    """Returns basic salary for the selected employee to autocomplete create forms."""
    emp = Employee.query.get_or_404(employee_id)
    return jsonify({
        "employee_id": emp.id,
        "full_name": emp.full_name,
        "base_salary": float(emp.salary or 0),
        "department": emp.department.name if emp.department else "Unassigned",
    })

