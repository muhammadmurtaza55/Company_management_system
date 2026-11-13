"""
Admin Forms Module.

Provides forms for managing departments, employees, attendance, tasks, and payroll.
"""

from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DecimalField,
    DateField,
    IntegerField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class DepartmentForm(FlaskForm):
    """Department creation and edit form."""
    name = StringField(
        "Department Name",
        validators=[DataRequired(message="Department name is required."), Length(max=100)],
        render_kw={"placeholder": "e.g. Engineering, Human Resources, Finance"},
    )
    code = StringField(
        "Department Code",
        validators=[DataRequired(message="Department code is required."), Length(max=20)],
        render_kw={"placeholder": "e.g. ENG, HR, FIN"},
    )
    description = TextAreaField(
        "Description",
        validators=[Optional()],
        render_kw={"placeholder": "Brief departmental overview and responsibilities", "rows": 3},
    )
    submit = SubmitField("Save Department")


class EmployeeForm(FlaskForm):
    """Employee creation and edit form."""
    first_name = StringField(
        "First Name",
        validators=[DataRequired(message="First name is required."), Length(max=64)],
        render_kw={"placeholder": "e.g. John"},
    )
    last_name = StringField(
        "Last Name",
        validators=[DataRequired(message="Last name is required."), Length(max=64)],
        render_kw={"placeholder": "e.g. Doe"},
    )
    job_title = StringField(
        "Job Title",
        validators=[DataRequired(message="Job title is required."), Length(max=100)],
        render_kw={"placeholder": "e.g. Senior Software Engineer"},
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
    )
    salary = DecimalField(
        "Monthly Salary ($)",
        places=2,
        validators=[Optional(), NumberRange(min=0, message="Salary must be non-negative.")],
        render_kw={"placeholder": "e.g. 7500.00"},
    )
    hire_date = DateField(
        "Hire Date",
        default=date.today,
        validators=[Optional()],
    )
    status = SelectField(
        "Employment Status",
        choices=[
            ("active", "Active"),
            ("on_leave", "On Leave"),
            ("terminated", "Terminated"),
        ],
        default="active",
        validators=[DataRequired()],
    )
    submit = SubmitField("Save Employee")


class TaskForm(FlaskForm):
    """Task creation and assignment form."""
    title = StringField(
        "Task Title",
        validators=[DataRequired(message="Task title is required."), Length(max=150)],
        render_kw={"placeholder": "e.g. Deploy cloud migration script"},
    )
    description = TextAreaField(
        "Description",
        validators=[Optional()],
        render_kw={"placeholder": "Detailed task instructions and acceptance criteria", "rows": 3},
    )
    assigned_to_id = SelectField(
        "Assign To",
        coerce=int,
        validators=[Optional()],
    )
    priority = SelectField(
        "Priority",
        choices=[
            ("low", "Low Priority"),
            ("medium", "Medium Priority"),
            ("high", "High Priority"),
            ("urgent", "Urgent Priority"),
        ],
        default="medium",
        validators=[DataRequired()],
    )
    status = SelectField(
        "Task Status",
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        validators=[DataRequired()],
    )
    due_date = DateField(
        "Due Date",
        validators=[Optional()],
    )
    submit = SubmitField("Save Task")


class AttendanceForm(FlaskForm):
    """Attendance log form."""
    employee_id = SelectField(
        "Employee",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    date = DateField(
        "Date",
        default=date.today,
        validators=[DataRequired(message="Date is required.")],
    )
    status = SelectField(
        "Attendance Status",
        choices=[
            ("present", "Present"),
            ("absent", "Absent"),
            ("late", "Late Arrival"),
            ("half_day", "Half Day"),
            ("on_leave", "On Leave"),
        ],
        default="present",
        validators=[DataRequired()],
    )
    notes = StringField(
        "Notes / Remarks",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "e.g. Remote work, approved sick leave, etc."},
    )
    submit = SubmitField("Record Attendance")


class PayrollForm(FlaskForm):
    """Payroll disbursement form."""
    employee_id = SelectField(
        "Employee",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    month = SelectField(
        "Payroll Month",
        coerce=int,
        choices=[
            (1, "January"), (2, "February"), (3, "March"), (4, "April"),
            (5, "May"), (6, "June"), (7, "July"), (8, "August"),
            (9, "September"), (10, "October"), (11, "November"), (12, "December"),
        ],
        default=date.today().month,
        validators=[DataRequired()],
    )
    year = IntegerField(
        "Payroll Year",
        default=date.today().year,
        validators=[DataRequired(), NumberRange(min=2020, max=2100)],
    )
    base_salary = DecimalField(
        "Base Salary ($)",
        places=2,
        validators=[DataRequired(message="Base salary is required."), NumberRange(min=0)],
        render_kw={"placeholder": "e.g. 5000.00"},
    )
    bonus = DecimalField(
        "Bonus ($)",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0)],
    )
    deductions = DecimalField(
        "Deductions ($)",
        places=2,
        default=0.00,
        validators=[Optional(), NumberRange(min=0)],
    )
    status = SelectField(
        "Payment Status",
        choices=[
            ("paid", "Paid"),
            ("pending", "Pending"),
            ("processing", "Processing"),
        ],
        default="paid",
        validators=[DataRequired()],
    )
    payment_date = DateField(
        "Disbursement Date",
        default=date.today,
        validators=[Optional()],
    )
    submit = SubmitField("Record Payroll")

