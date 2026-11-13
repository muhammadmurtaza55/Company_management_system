"""
Task Blueprint Routes.

Implements the Task Management Module:
- Task creation, editing, assignment, and deletion.
- Deadlines, priorities (Low, Medium, High, Urgent), and statuses (Pending, In Progress, Completed, Cancelled).
- Scoping: Admin (all), Manager (department staff), Employee (own assigned tasks).
- Dedicated Employee Task Dashboard (/tasks/my-tasks).
- Quick status transitions.
"""

from datetime import datetime, timezone, date
from flask import (
    render_template,
    flash,
    redirect,
    url_for,
    request,
    abort,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from app.blueprints.task import task_bp
from app.blueprints.task.forms import TaskForm, TaskStatusUpdateForm
from app.extensions import db
from app.models.task import Task
from app.models.employee import Employee
from app.models.department import Department


def _get_manager_dept_id():
    """Returns department ID managed by current user, if manager."""
    if current_user.is_manager:
        emp = getattr(current_user, "employee", None)
        return emp.department_id if emp else None
    return None


def _check_task_permission(task: Task, write: bool = False):
    """
    Enforces role-based permissions on task operations:
    - Admin: Full access.
    - Manager: Access if assigned employee belongs to manager's department or created by manager.
    - Employee: View/Update status if assigned to self. Write/delete not permitted.
    """
    if current_user.is_admin:
        return

    emp = getattr(current_user, "employee", None)

    if current_user.is_manager:
        mgr_dept_id = _get_manager_dept_id()
        if not mgr_dept_id:
            abort(403, description="Access denied. You are not assigned to manage any department.")
        # If task assigned to someone, they must be in manager's department
        if task.assignee and task.assignee.department_id != mgr_dept_id:
            abort(403, description="Access denied. You can only manage tasks within your department.")
        return

    if current_user.is_employee:
        if write:
            abort(403, description="Employees are not authorized to edit or delete task definitions.")
        if not emp or task.assigned_to_id != emp.id:
            abort(403, description="Access denied. You can only view tasks assigned to you.")
        return

    abort(403, description="Unauthorized access to task.")


# -----------------------------------------------------------------------------
# 1. Tasks Directory & Overview (Admin & Manager)
# -----------------------------------------------------------------------------
@task_bp.route("", methods=["GET"], strict_slashes=False)
@task_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def index():
    """
    Main tasks directory:
    - Employees are redirected to their personalized Task Dashboard (/tasks/my-tasks).
    - Admins and Managers view the management task board with filters and metrics.
    """
    if current_user.is_employee:
        return redirect(url_for("task.my_tasks"))

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    # Base query
    query = Task.query.outerjoin(Employee, Task.assigned_to_id == Employee.id)

    if current_user.is_manager:
        query = query.filter(Employee.department_id == mgr_dept_id)

    # Calculate overall task metrics before filters
    all_scoped = query.all()
    today = date.today()
    metrics = {
        "total": len(all_scoped),
        "pending": sum(1 for t in all_scoped if t.status == "pending"),
        "in_progress": sum(1 for t in all_scoped if t.status == "in_progress"),
        "completed": sum(1 for t in all_scoped if t.status == "completed"),
        "overdue": sum(1 for t in all_scoped if t.is_overdue),
    }

    # Filters
    search_q = request.args.get("search", "").strip()
    if search_q:
        query = query.filter(
            or_(
                Task.title.ilike(f"%{search_q}%"),
                Task.description.ilike(f"%{search_q}%"),
                Employee.first_name.ilike(f"%{search_q}%"),
                Employee.last_name.ilike(f"%{search_q}%"),
            )
        )

    status_f = request.args.get("status", "").strip()
    if status_f in Task.STATUSES:
        query = query.filter(Task.status == status_f)

    priority_f = request.args.get("priority", "").strip()
    if priority_f in Task.PRIORITIES:
        query = query.filter(Task.priority == priority_f)

    dept_id = request.args.get("department_id", type=int)
    if dept_id and current_user.is_admin and dept_id > 0:
        query = query.filter(Employee.department_id == dept_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id and assignee_id > 0:
        query = query.filter(Task.assigned_to_id == assignee_id)

    # Pagination
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(
        Task.status == "completed",
        Task.due_date.asc().nullslast(),
        Task.id.desc(),
    ).paginate(page=page, per_page=15, error_out=False)

    departments = Department.query.order_by(Department.name.asc()).all() if current_user.is_admin else []
    employees_query = Employee.query.filter(Employee.status == "active")
    if current_user.is_manager:
        employees_query = employees_query.filter(Employee.department_id == mgr_dept_id)
    assignee_choices = employees_query.order_by(Employee.last_name.asc()).all()

    return render_template(
        "task/index.html",
        tasks=pagination.items,
        pagination=pagination,
        metrics=metrics,
        departments=departments,
        assignee_choices=assignee_choices,
        active_filters={
            "search": search_q,
            "status": status_f,
            "priority": priority_f,
            "department_id": dept_id or 0,
            "assignee_id": assignee_id or 0,
        },
    )


# -----------------------------------------------------------------------------
# 2. Employee Task Dashboard (My Tasks)
# -----------------------------------------------------------------------------
@task_bp.route("/my-tasks", methods=["GET"], strict_slashes=False)
@login_required
def my_tasks():
    """
    Dedicated Employee Task Dashboard:
    Displays pending, in-progress, and completed tasks assigned to the logged-in employee.
    Provides one-click action buttons to start or complete tasks.
    """
    emp = getattr(current_user, "employee", None)
    if not emp:
        flash("You do not have an active employee profile linked to your user account.", "warning")
        return redirect(url_for("main.index"))

    assigned_tasks = (
        Task.query.filter_by(assigned_to_id=emp.id)
        .order_by(Task.due_date.asc().nullslast(), Task.id.desc())
        .all()
    )

    pending_tasks = [t for t in assigned_tasks if t.status == "pending"]
    in_progress_tasks = [t for t in assigned_tasks if t.status == "in_progress"]
    completed_tasks = [t for t in assigned_tasks if t.status == "completed"]

    metrics = {
        "total": len(assigned_tasks),
        "pending": len(pending_tasks),
        "in_progress": len(in_progress_tasks),
        "completed": len(completed_tasks),
        "overdue": sum(1 for t in assigned_tasks if t.is_overdue),
    }

    return render_template(
        "task/my_tasks.html",
        emp=emp,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        metrics=metrics,
    )


# -----------------------------------------------------------------------------
# 3. Create Task (Admin & Manager)
# -----------------------------------------------------------------------------
@task_bp.route("/create", methods=["GET", "POST"], strict_slashes=False)
@login_required
def create():
    """
    Creates and assigns a new task.
    - Admin: can assign to any employee.
    - Manager: can assign to employees within their department.
    """
    if current_user.is_employee:
        abort(403, description="Employees cannot create and assign tasks.")

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    form = TaskForm()
    emp_query = Employee.query.filter(Employee.status == "active")
    if current_user.is_manager:
        emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)

    employees = emp_query.order_by(Employee.last_name.asc()).all()
    form.assigned_to_id.choices = [(0, "Unassigned / General")] + [
        (e.id, f"{e.full_name} ({e.job_title}) [{e.department.name if e.department else 'No Dept'}]")
        for e in employees
    ]

    # Pre-select employee if passed in query string
    pre_emp_id = request.args.get("employee_id", type=int)
    if request.method == "GET" and pre_emp_id:
        form.assigned_to_id.data = pre_emp_id

    if form.validate_on_submit():
        assignee_id = form.assigned_to_id.data if form.assigned_to_id.data != 0 else None

        # Verify manager cannot assign outside department
        if current_user.is_manager and assignee_id:
            target_emp = Employee.query.get(assignee_id)
            if not target_emp or target_emp.department_id != mgr_dept_id:
                flash("You can only assign tasks to employees in your department.", "danger")
                return render_template("task/form.html", form=form)

        new_task = Task(
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            assigned_to_id=assignee_id,
            created_by_id=current_user.id,
            priority=form.priority.data,
            status=form.status.data,
            due_date=form.due_date.data,
        )

        if form.status.data == "completed":
            new_task.completed_at = datetime.now(timezone.utc)

        db.session.add(new_task)
        db.session.commit()

        flash(f"Task '{new_task.title}' created and assigned successfully!", "success")
        return redirect(url_for("task.index"))

    return render_template("task/form.html", form=form, is_edit=False)


# -----------------------------------------------------------------------------
# 4. View Task Details
# -----------------------------------------------------------------------------
@task_bp.route("/<int:id>", methods=["GET"], strict_slashes=False)
@login_required
def detail(id: int):
    """View full task specifications, deadlines, and status."""
    task = Task.query.get_or_404(id)
    _check_task_permission(task, write=False)

    status_form = TaskStatusUpdateForm(obj=task)
    return render_template("task/detail.html", task=task, status_form=status_form)


# -----------------------------------------------------------------------------
# 5. Edit Task (Admin & Manager)
# -----------------------------------------------------------------------------
@task_bp.route("/<int:id>/edit", methods=["GET", "POST"], strict_slashes=False)
@login_required
def edit(id: int):
    """Edits an existing task."""
    task = Task.query.get_or_404(id)
    _check_task_permission(task, write=True)

    mgr_dept_id = _get_manager_dept_id() if current_user.is_manager else None

    form = TaskForm(obj=task)
    emp_query = Employee.query.filter(Employee.status == "active")
    if current_user.is_manager:
        emp_query = emp_query.filter(Employee.department_id == mgr_dept_id)

    employees = emp_query.order_by(Employee.last_name.asc()).all()
    form.assigned_to_id.choices = [(0, "Unassigned / General")] + [
        (e.id, f"{e.full_name} ({e.job_title})") for e in employees
    ]

    if form.validate_on_submit():
        assignee_id = form.assigned_to_id.data if form.assigned_to_id.data != 0 else None

        if current_user.is_manager and assignee_id:
            target_emp = Employee.query.get(assignee_id)
            if not target_emp or target_emp.department_id != mgr_dept_id:
                flash("You can only assign tasks to employees in your department.", "danger")
                return render_template("task/form.html", form=form, task=task, is_edit=True)

        task.title = form.title.data.strip()
        task.description = form.description.data.strip() if form.description.data else None
        task.assigned_to_id = assignee_id
        task.priority = form.priority.data
        task.due_date = form.due_date.data

        # Status transition
        old_status = task.status
        new_status = form.status.data
        task.status = new_status

        if new_status == "completed" and old_status != "completed":
            task.completed_at = datetime.now(timezone.utc)
        elif new_status != "completed":
            task.completed_at = None

        task.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        flash(f"Task '{task.title}' updated successfully.", "success")
        return redirect(url_for("task.detail", id=task.id))

    return render_template("task/form.html", form=form, task=task, is_edit=True)


# -----------------------------------------------------------------------------
# 6. Quick Status Transition (Assignee, Manager, Admin)
# -----------------------------------------------------------------------------
@task_bp.route("/<int:id>/status", methods=["POST"], strict_slashes=False)
@login_required
def update_status(id: int):
    """
    Updates status for a task:
    - Assigned employee can mark task in_progress or completed.
    - Managers & Admins can change status to any value.
    """
    task = Task.query.get_or_404(id)
    _check_task_permission(task, write=False)

    new_status = request.form.get("status", "").strip()
    if new_status not in Task.STATUSES:
        flash("Invalid task status specified.", "danger")
        return redirect(request.referrer or url_for("task.index"))

    task.status = new_status
    if new_status == "completed":
        task.completed_at = datetime.now(timezone.utc)
    else:
        task.completed_at = None

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    flash(f"Task '{task.title}' marked as {new_status.replace('_', ' ').title()}!", "success")
    return redirect(request.referrer or url_for("task.detail", id=task.id))


# -----------------------------------------------------------------------------
# 7. Delete Task (Admin & Manager)
# -----------------------------------------------------------------------------
@task_bp.route("/<int:id>/delete", methods=["POST"], strict_slashes=False)
@login_required
def delete(id: int):
    """Deletes a task."""
    task = Task.query.get_or_404(id)
    _check_task_permission(task, write=True)

    title = task.title
    db.session.delete(task)
    db.session.commit()

    flash(f"Task '{title}' has been deleted.", "info")
    return redirect(url_for("task.index"))

