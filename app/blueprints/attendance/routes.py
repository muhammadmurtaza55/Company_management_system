"""
Attendance Blueprint Routes.

Implements the complete Attendance Management Module:
- Employee self check-in and check-out with time validation and duplicate prevention.
- Late arrival detection (standard start threshold: 9:30 AM).
- Role-based scoping (Admin: all, Manager: department, Employee: self).
- Daily attendance records and monthly attendance summaries.
- Safe absence handling: Does not auto-mark employees absent before working day concludes.
- Leave request submission and approval/rejection workflows with attendance syncing.
- Daily, monthly, and late arrival reports.
"""

from datetime import datetime, timezone, date, time, timedelta
from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func, or_
from app.blueprints.attendance import attendance_bp
from app.blueprints.attendance.forms import (
    LeaveRequestForm,
    LeaveReviewForm,
    ManualAttendanceForm,
    DailyReportFilterForm,
    MonthlyReportFilterForm,
)
from app.extensions import db
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.employee import Employee
from app.models.department import Department
from app.utils.decorators import admin_required


def _get_manager_dept_id():
    """Returns department ID managed by current user, if manager."""
    if current_user.is_manager:
        emp = getattr(current_user, "employee", None)
        return emp.department_id if emp else None
    return None


@attendance_bp.route("", methods=["GET"], strict_slashes=False)
@attendance_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """
    Main Attendance Hub tailored to user role:
    - Employee: Personal check-in/out widget, today's status, monthly summary, recent logs.
    - Manager: Department attendance today, staff status, pending leave requests for department.
    - Admin: Company-wide attendance stats today, live roster, company pending leaves.
    """
    today = date.today()
    now_time = datetime.now().time()
    emp = getattr(current_user, "employee", None)

    # 1. Employee View (or Manager's personal widget)
    today_attendance = None
    monthly_stats = None
    recent_history = []
    my_leaves = []

    if emp:
        today_attendance = Attendance.query.filter_by(
            employee_id=emp.id, date=today
        ).first()

        # Monthly summary for employee
        first_of_month = today.replace(day=1)
        month_logs = Attendance.query.filter(
            Attendance.employee_id == emp.id,
            Attendance.date >= first_of_month,
            Attendance.date <= today,
        ).all()

        days_present = sum(1 for a in month_logs if a.status in ("present", "late", "half_day"))
        days_late = sum(1 for a in month_logs if a.status == "late" or a.is_late)
        days_leave = sum(1 for a in month_logs if a.status == "on_leave")
        days_absent = sum(1 for a in month_logs if a.status == "absent")

        monthly_stats = {
            "days_present": days_present,
            "days_late": days_late,
            "days_leave": days_leave,
            "days_absent": days_absent,
            "total_logs": len(month_logs),
        }

        recent_history = (
            Attendance.query.filter_by(employee_id=emp.id)
            .order_by(Attendance.date.desc())
            .limit(10)
            .all()
        )

        my_leaves = (
            LeaveRequest.query.filter_by(employee_id=emp.id)
            .order_by(LeaveRequest.created_at.desc())
            .limit(5)
            .all()
        )

    # 2. Manager / Admin View
    dept_roster = []
    pending_leaves = []
    overview_stats = {}

    if current_user.is_admin or current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()

        # Build employee query
        emp_query = Employee.query.filter(Employee.status == "active")
        if current_user.is_manager:
            emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)

        active_employees = emp_query.order_by(Employee.last_name.asc()).all()
        active_emp_ids = [e.id for e in active_employees]

        # Fetch today's attendance records for these employees
        today_records = {
            a.employee_id: a
            for a in Attendance.query.filter(
                Attendance.employee_id.in_(active_emp_ids), Attendance.date == today
            ).all()
        } if active_emp_ids else {}

        # Build roster with safe today status
        present_cnt = 0
        late_cnt = 0
        on_leave_cnt = 0
        not_checked_in_cnt = 0

        for employee in active_employees:
            rec = today_records.get(employee.id)
            if rec:
                status = rec.status
                if status == "present":
                    present_cnt += 1
                elif status == "late":
                    late_cnt += 1
                    present_cnt += 1
                elif status == "on_leave":
                    on_leave_cnt += 1
            else:
                # Rule: Do not automatically mark employees absent before the working day is over!
                status = "not_checked_in"
                not_checked_in_cnt += 1

            dept_roster.append({
                "employee": employee,
                "attendance": rec,
                "status": status,
            })

        overview_stats = {
            "total_staff": len(active_employees),
            "present_today": present_cnt,
            "late_today": late_cnt,
            "on_leave_today": on_leave_cnt,
            "not_checked_in": not_checked_in_cnt,
        }

        # Pending Leave Requests for review
        leave_query = LeaveRequest.query.filter_by(status="pending")
        if current_user.is_manager:
            leave_query = leave_query.join(Employee).filter(
                Employee.department_id == mgr_dept_id
            )
        pending_leaves = leave_query.order_by(LeaveRequest.created_at.asc()).limit(10).all()

    return render_template(
        "attendance/index.html",
        today=today,
        now_time=now_time,
        emp=emp,
        today_attendance=today_attendance,
        monthly_stats=monthly_stats,
        recent_history=recent_history,
        my_leaves=my_leaves,
        overview_stats=overview_stats,
        dept_roster=dept_roster,
        pending_leaves=pending_leaves,
        leave_form=LeaveRequestForm(),
    )


@attendance_bp.route("/check-in", methods=["POST"], strict_slashes=False)
@login_required
def check_in():
    """
    Records employee check-in for today.
    - Prevents duplicate check-in.
    - Validates arrival time against 9:30 AM standard (marks late if past threshold).
    - Stores time consistently in PostgreSQL.
    """
    emp = getattr(current_user, "employee", None)
    if not emp:
        flash("You do not have an active employee profile linked to your user account.", "danger")
        return redirect(url_for("attendance.index"))

    today = date.today()
    now_time = datetime.now().time()

    # Check for existing record
    existing = Attendance.query.filter_by(employee_id=emp.id, date=today).first()
    if existing and existing.check_in is not None:
        flash(
            f"You have already checked in for today at {existing.check_in.strftime('%I:%M %p')}.",
            "warning",
        )
        return redirect(url_for("attendance.index"))

    if existing and existing.status == "on_leave":
        flash("You are registered as on approved leave for today.", "warning")
        return redirect(url_for("attendance.index"))

    # Determine status (Threshold: 9:30 AM)
    standard_start = time(9, 30, 0)
    is_late = now_time > standard_start
    status = "late" if is_late else "present"

    if existing:
        existing.check_in = now_time
        existing.status = status
        record = existing
    else:
        record = Attendance(
            employee_id=emp.id,
            date=today,
            status=status,
            check_in=now_time,
        )
        db.session.add(record)

    db.session.commit()

    time_str = now_time.strftime("%I:%M %p")
    if is_late:
        flash(f"Checked in at {time_str}. Arrival recorded as Late.", "warning")
    else:
        flash(f"Checked in successfully at {time_str}. Have a productive day!", "success")

    return redirect(url_for("attendance.index"))


@attendance_bp.route("/check-out", methods=["POST"], strict_slashes=False)
@login_required
def check_out():
    """
    Records employee check-out for today.
    - Ensures check-in occurred first.
    - Ensures check-out happens after check-in.
    - Prevents duplicate check-out.
    """
    emp = getattr(current_user, "employee", None)
    if not emp:
        flash("You do not have an active employee profile linked to your user account.", "danger")
        return redirect(url_for("attendance.index"))

    today = date.today()
    att = Attendance.query.filter_by(employee_id=emp.id, date=today).first()

    if not att or not att.check_in:
        flash("You must check in first before checking out.", "danger")
        return redirect(url_for("attendance.index"))

    if att.check_out is not None:
        flash(
            f"You have already checked out for today at {att.check_out.strftime('%I:%M %p')}.",
            "warning",
        )
        return redirect(url_for("attendance.index"))

    now_time = datetime.now().time()
    if now_time < att.check_in:
        flash("Check-out time cannot be prior to check-in time.", "danger")
        return redirect(url_for("attendance.index"))

    att.check_out = now_time
    db.session.commit()

    duration = att.work_duration_formatted
    flash(
        f"Checked out successfully at {now_time.strftime('%I:%M %p')}! Total work time: {duration}.",
        "success",
    )
    return redirect(url_for("attendance.index"))


@attendance_bp.route("/history", methods=["GET"], strict_slashes=False)
@login_required
def history():
    """
    Displays attendance history.
    - Employee: View own attendance history only.
    - Manager: View department staff attendance history.
    - Admin: View all company attendance history with filters.
    """
    emp = getattr(current_user, "employee", None)

    # Scoping
    query = Attendance.query.join(Employee)

    if current_user.is_employee:
        if not emp:
            flash("No employee profile found.", "warning")
            return redirect(url_for("main.index"))
        query = query.filter(Attendance.employee_id == emp.id)
    elif current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        query = query.filter(Employee.department_id == mgr_dept_id)

    # Filters
    emp_id = request.args.get("employee_id", type=int)
    if emp_id and (current_user.is_admin or current_user.is_manager):
        query = query.filter(Attendance.employee_id == emp_id)

    status = request.args.get("status", "").strip()
    if status in ("present", "late", "absent", "half_day", "on_leave"):
        query = query.filter(Attendance.status == status)

    from_date = request.args.get("from_date")
    if from_date:
        try:
            d_from = datetime.strptime(from_date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date >= d_from)
        except ValueError:
            pass

    to_date = request.args.get("to_date")
    if to_date:
        try:
            d_to = datetime.strptime(to_date, "%Y-%m-%d").date()
            query = query.filter(Attendance.date <= d_to)
        except ValueError:
            pass

    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Attendance.date.desc(), Attendance.id.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    # Candidates for employee filter dropdown
    employee_choices = []
    if current_user.is_admin:
        employee_choices = Employee.query.order_by(Employee.last_name.asc()).all()
    elif current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        employee_choices = (
            Employee.query.filter_by(department_id=mgr_dept_id)
            .order_by(Employee.last_name.asc())
            .all()
        )

    return render_template(
        "attendance/history.html",
        records=pagination.items,
        pagination=pagination,
        employee_choices=employee_choices,
        active_filters={
            "employee_id": emp_id or 0,
            "status": status,
            "from_date": from_date or "",
            "to_date": to_date or "",
        },
    )


@attendance_bp.route("/reports/daily", methods=["GET"], strict_slashes=False)
@login_required
def daily_report():
    """
    Daily attendance report.
    Respects Rule: Do not automatically mark employees absent before the working day is over.
    - For today: Unrecorded staff are displayed as 'Not Checked In (Pending)'.
    - For past dates: Unrecorded active staff are counted as 'Absent'.
    """
    if current_user.is_employee:
        # Employees view their own history
        return redirect(url_for("attendance.history"))

    report_date_str = request.args.get("date", "").strip()
    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date() if report_date_str else date.today()
    except ValueError:
        report_date = date.today()

    dept_id = request.args.get("department_id", type=int)
    status_filter = request.args.get("status", "").strip()

    # Employee scope
    emp_query = Employee.query.filter(Employee.status == "active")
    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)
    elif current_user.is_admin and dept_id and dept_id > 0:
        emp_query = emp_query.filter(Employee.department_id == dept_id)

    employees = emp_query.order_by(Employee.last_name.asc()).all()
    emp_ids = [e.id for e in employees]

    # Fetch attendance records for this date
    records = {
        a.employee_id: a
        for a in Attendance.query.filter(
            Attendance.employee_id.in_(emp_ids), Attendance.date == report_date
        ).all()
    } if emp_ids else {}

    is_today = (report_date == date.today())
    is_past = (report_date < date.today())

    roster = []
    counts = {
        "total": len(employees),
        "present": 0,
        "late": 0,
        "on_leave": 0,
        "absent": 0,
        "not_checked_in": 0,
    }

    for emp in employees:
        att = records.get(emp.id)
        if att:
            st = att.status
            if st == "present":
                counts["present"] += 1
            elif st == "late":
                counts["late"] += 1
                counts["present"] += 1
            elif st == "on_leave":
                counts["on_leave"] += 1
            elif st == "absent":
                counts["absent"] += 1
        else:
            if is_today:
                # Not marked absent before the working day ends
                st = "not_checked_in"
                counts["not_checked_in"] += 1
            elif is_past:
                st = "absent"
                counts["absent"] += 1
            else:
                st = "scheduled"

        if not status_filter or status_filter == st:
            roster.append({
                "employee": emp,
                "attendance": att,
                "status": st,
            })

    departments = Department.query.order_by(Department.name.asc()).all()

    return render_template(
        "attendance/daily_report.html",
        today=date.today(),
        report_date=report_date,
        is_today=is_today,
        is_past=is_past,
        roster=roster,
        counts=counts,
        departments=departments,
        selected_dept_id=dept_id or 0,
        selected_status=status_filter,
    )


@attendance_bp.route("/reports/monthly", methods=["GET"], strict_slashes=False)
@login_required
def monthly_report():
    """
    Monthly attendance report with employee-wise attendance rates and breakdown.
    """
    if current_user.is_employee:
        return redirect(url_for("attendance.history"))

    today = date.today()
    month = request.args.get("month", today.month, type=int)
    year = request.args.get("year", today.year, type=int)
    dept_id = request.args.get("department_id", type=int)

    # Determine date bounds
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    # Scoping
    emp_query = Employee.query.filter(Employee.status == "active")
    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)
    elif current_user.is_admin and dept_id and dept_id > 0:
        emp_query = emp_query.filter(Employee.department_id == dept_id)

    employees = emp_query.order_by(Employee.last_name.asc()).all()
    emp_ids = [e.id for e in employees]

    # Attendance logs for the month
    records = Attendance.query.filter(
        Attendance.employee_id.in_(emp_ids),
        Attendance.date >= start_date,
        Attendance.date <= end_date,
    ).all() if emp_ids else []

    emp_logs = {}
    for r in records:
        emp_logs.setdefault(r.employee_id, []).append(r)

    # Business days up to today (or end of month)
    eval_end = min(today, end_date) if today >= start_date else start_date
    working_days = sum(
        1 for i in range((eval_end - start_date).days + 1)
        if (start_date + timedelta(days=i)).weekday() < 5
    ) if eval_end >= start_date else 1

    summary_rows = []
    tot_p = 0
    tot_l = 0
    tot_lv = 0
    tot_a = 0

    for emp in employees:
        logs = emp_logs.get(emp.id, [])
        p_count = sum(1 for l in logs if l.status in ("present", "late", "half_day"))
        l_count = sum(1 for l in logs if l.status == "late" or l.is_late)
        lv_count = sum(1 for l in logs if l.status == "on_leave")
        a_count = sum(1 for l in logs if l.status == "absent")
        tot_secs = sum(l.work_duration_seconds for l in logs)

        rate = (p_count / max(1, working_days)) * 100

        tot_p += p_count
        tot_l += l_count
        tot_lv += lv_count
        tot_a += a_count

        summary_rows.append({
            "employee": emp,
            "present_days": p_count,
            "late_days": l_count,
            "leave_days": lv_count,
            "absent_days": a_count,
            "total_hours": round(tot_secs / 3600, 1),
            "attendance_rate": min(100.0, round(rate, 1)),
        })

    departments = Department.query.order_by(Department.name.asc()).all()

    return render_template(
        "attendance/monthly_report.html",
        month=month,
        year=year,
        start_date=start_date,
        end_date=end_date,
        working_days=working_days,
        summary_rows=summary_rows,
        departments=departments,
        selected_dept_id=dept_id or 0,
        totals={
            "present": tot_p,
            "late": tot_l,
            "leave": tot_lv,
            "absent": tot_a,
        },
    )


@attendance_bp.route("/reports/late", methods=["GET"], strict_slashes=False)
@login_required
def late_report():
    """
    Late arrival tracking report with minutes late and notes.
    """
    if current_user.is_employee:
        return redirect(url_for("attendance.history"))

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

    dept_id = request.args.get("department_id", type=int)

    query = (
        Attendance.query.join(Employee)
        .filter(
            Attendance.date >= d_from,
            Attendance.date <= d_to,
            or_(Attendance.status == "late", Attendance.check_in > time(9, 30, 0)),
        )
    )

    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        query = query.filter(Employee.department_id == mgr_dept_id)
    elif current_user.is_admin and dept_id and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    late_records = query.order_by(Attendance.date.desc(), Attendance.check_in.desc()).all()
    departments = Department.query.order_by(Department.name.asc()).all()

    total_late_minutes = sum(r.minutes_late for r in late_records)

    return render_template(
        "attendance/late_report.html",
        records=late_records,
        from_date=d_from,
        to_date=d_to,
        departments=departments,
        selected_dept_id=dept_id or 0,
        total_late_minutes=total_late_minutes,
    )


# -----------------------------------------------------------------------------
# Leave Management Workflow
# -----------------------------------------------------------------------------
@attendance_bp.route("/leaves", methods=["GET"], strict_slashes=False)
@login_required
def leaves():
    """
    Leave requests list:
    - Employee: view own leave requests.
    - Manager: review department leave requests + view own.
    - Admin: view and manage all company leave requests.
    """
    status_filter = request.args.get("status", "").strip()
    emp = getattr(current_user, "employee", None)

    query = LeaveRequest.query.join(Employee)

    if current_user.is_employee:
        if not emp:
            flash("No employee profile found.", "warning")
            return redirect(url_for("main.index"))
        query = query.filter(LeaveRequest.employee_id == emp.id)
    elif current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        query = query.filter(Employee.department_id == mgr_dept_id)

    if status_filter in ("pending", "approved", "rejected", "cancelled"):
        query = query.filter(LeaveRequest.status == status_filter)

    leave_list = query.order_by(
        LeaveRequest.status == "pending", LeaveRequest.start_date.desc()
    ).all()

    return render_template(
        "attendance/leaves.html",
        leaves=leave_list,
        status_filter=status_filter,
        review_form=LeaveReviewForm(),
    )


@attendance_bp.route("/leaves/request", methods=["GET", "POST"], strict_slashes=False)
@login_required
def submit_leave():
    """
    Submits a new leave request.
    Validates date ranges and prevents overlapping requests.
    """
    emp = getattr(current_user, "employee", None)
    if not emp:
        flash("You do not have an active employee profile linked to your user account.", "danger")
        return redirect(url_for("attendance.index"))

    form = LeaveRequestForm()

    if form.validate_on_submit():
        start = form.start_date.data
        end = form.end_date.data

        # Check for overlapping active leave requests
        overlap = LeaveRequest.query.filter(
            LeaveRequest.employee_id == emp.id,
            LeaveRequest.status.in_(["pending", "approved"]),
            LeaveRequest.start_date <= end,
            LeaveRequest.end_date >= start,
        ).first()

        if overlap:
            flash(
                f"You already have a {overlap.status} leave request covering {overlap.start_date} to {overlap.end_date}.",
                "danger",
            )
            return render_template("attendance/leave_form.html", form=form)

        leave_req = LeaveRequest(
            employee_id=emp.id,
            leave_type=form.leave_type.data,
            start_date=start,
            end_date=end,
            reason=form.reason.data.strip(),
            status="pending",
        )
        db.session.add(leave_req)
        db.session.commit()

        flash(
            f"Leave request for {leave_req.duration_days} day(s) submitted successfully!",
            "success",
        )
        return redirect(url_for("attendance.leaves"))

    return render_template("attendance/leave_form.html", form=form)


@attendance_bp.route("/leaves/<int:id>/approve", methods=["POST"], strict_slashes=False)
@login_required
def approve_leave(id: int):
    """
    Approves a pending leave request (Admin or Department Manager).
    Automatically creates/updates Attendance records as 'on_leave' for the duration.
    """
    leave_req = LeaveRequest.query.get_or_404(id)

    # Permission check
    if not current_user.is_admin:
        mgr_dept_id = _get_manager_dept_id()
        if not current_user.is_manager or leave_req.employee.department_id != mgr_dept_id:
            abort(403, description="Unauthorized to approve this leave request.")

    leave_req.status = "approved"
    leave_req.reviewed_by_id = current_user.id
    leave_req.reviewed_at = datetime.now(timezone.utc)
    leave_req.review_notes = request.form.get("review_notes", "").strip() or None

    # Sync attendance records for each day of leave
    curr = leave_req.start_date
    while curr <= leave_req.end_date:
        att = Attendance.query.filter_by(employee_id=leave_req.employee_id, date=curr).first()
        if att:
            att.status = "on_leave"
            att.notes = f"Approved Leave ({leave_req.leave_type.title()})"
        else:
            att = Attendance(
                employee_id=leave_req.employee_id,
                date=curr,
                status="on_leave",
                notes=f"Approved Leave ({leave_req.leave_type.title()})",
            )
            db.session.add(att)
        curr += timedelta(days=1)

    db.session.commit()
    flash(f"Leave request #{leave_req.id} for {leave_req.employee.full_name} approved.", "success")
    return redirect(url_for("attendance.leaves"))


@attendance_bp.route("/leaves/<int:id>/reject", methods=["POST"], strict_slashes=False)
@login_required
def reject_leave(id: int):
    """
    Rejects a pending leave request (Admin or Department Manager).
    """
    leave_req = LeaveRequest.query.get_or_404(id)

    if not current_user.is_admin:
        mgr_dept_id = _get_manager_dept_id()
        if not current_user.is_manager or leave_req.employee.department_id != mgr_dept_id:
            abort(403, description="Unauthorized to review this leave request.")

    leave_req.status = "rejected"
    leave_req.reviewed_by_id = current_user.id
    leave_req.reviewed_at = datetime.now(timezone.utc)
    leave_req.review_notes = request.form.get("review_notes", "").strip() or None

    db.session.commit()
    flash(f"Leave request #{leave_req.id} for {leave_req.employee.full_name} rejected.", "info")
    return redirect(url_for("attendance.leaves"))


# -----------------------------------------------------------------------------
# Manual Entry / Adjustment (Admin only)
# -----------------------------------------------------------------------------
@attendance_bp.route("/manual", methods=["GET", "POST"], strict_slashes=False)
@login_required
@admin_required
def manual_entry():
    """
    Allows Administrator to log or adjust employee attendance records manually.
    """
    form = ManualAttendanceForm()
    employees = Employee.query.order_by(Employee.last_name.asc()).all()
    form.employee_id.choices = [(0, "Select Employee...")] + [
        (e.id, f"{e.full_name} ({e.employee_id})") for e in employees
    ]

    if form.validate_on_submit():
        emp_id = form.employee_id.data
        att_date = form.date.data

        existing = Attendance.query.filter_by(employee_id=emp_id, date=att_date).first()
        if existing:
            existing.status = form.status.data
            existing.check_in = form.check_in.data
            existing.check_out = form.check_out.data
            existing.notes = form.notes.data
            flash(f"Attendance record updated for {existing.employee.full_name} on {att_date}.", "info")
        else:
            new_rec = Attendance(
                employee_id=emp_id,
                date=att_date,
                status=form.status.data,
                check_in=form.check_in.data,
                check_out=form.check_out.data,
                notes=form.notes.data,
            )
            db.session.add(new_rec)
            flash(f"Attendance record created for {att_date}.", "success")

        db.session.commit()
        return redirect(url_for("attendance.history"))

    return render_template("attendance/manual_form.html", form=form)
