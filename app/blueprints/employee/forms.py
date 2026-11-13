"""
Employee Blueprint Forms.

Provides forms with CSRF protection, validation, and dynamic dropdowns
for Employee creation, editing, and directory filtering.
"""

from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DecimalField,
    DateField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    Optional,
    NumberRange,
    ValidationError,
)
from sqlalchemy import func
from app.models.employee import Employee


class EmployeeBaseForm(FlaskForm):
    """Base form containing common fields for employee creation and editing."""

    employee_id = StringField(
        "Employee ID",
        validators=[
            DataRequired(message="Employee ID is required."),
            Length(min=2, max=32, message="Employee ID must be between 2 and 32 characters."),
        ],
        render_kw={"placeholder": "e.g. EMP-1001", "autocomplete": "off"},
    )
    first_name = StringField(
        "First Name",
        validators=[
            DataRequired(message="First name is required."),
            Length(max=64, message="First name cannot exceed 64 characters."),
        ],
        render_kw={"placeholder": "e.g. Sarah"},
    )
    last_name = StringField(
        "Last Name",
        validators=[
            DataRequired(message="Last name is required."),
            Length(max=64, message="Last name cannot exceed 64 characters."),
        ],
        render_kw={"placeholder": "e.g. Connor"},
    )
    email = StringField(
        "Corporate Email",
        validators=[
            DataRequired(message="Corporate email is required."),
            Email(message="Please enter a valid email address."),
            Length(max=120, message="Email cannot exceed 120 characters."),
        ],
        render_kw={"placeholder": "e.g. s.connor@company.com", "type": "email"},
    )
    phone = StringField(
        "Phone Number",
        validators=[
            Optional(),
            Length(max=32, message="Phone number cannot exceed 32 characters."),
        ],
        render_kw={"placeholder": "e.g. +1 (555) 234-5678"},
    )
    address = TextAreaField(
        "Residential Address",
        validators=[Optional()],
        render_kw={"placeholder": "Street address, City, State, Postal code", "rows": 3},
    )
    job_title = StringField(
        "Job Title",
        validators=[
            DataRequired(message="Job title is required."),
            Length(max=100, message="Job title cannot exceed 100 characters."),
        ],
        render_kw={"placeholder": "e.g. Lead Systems Engineer"},
    )
    department_id = SelectField(
        "Department Assignment",
        coerce=int,
        validators=[Optional()],
    )
    hire_date = DateField(
        "Joining Date",
        default=date.today,
        validators=[Optional()],
    )
    salary = DecimalField(
        "Base Salary (Monthly $)",
        places=2,
        validators=[
            Optional(),
            NumberRange(min=0, message="Base salary cannot be negative."),
        ],
        render_kw={"placeholder": "e.g. 8500.00"},
    )
    status = SelectField(
        "Employment Status",
        choices=[
            ("active", "Active"),
            ("on_leave", "On Leave"),
            ("terminated", "Terminated"),
        ],
        default="active",
        validators=[DataRequired(message="Please select employment status.")],
    )
    user_id = SelectField(
        "Link System User Account (Optional)",
        coerce=int,
        validators=[Optional()],
    )
    submit = SubmitField("Save Employee")


class EmployeeCreateForm(EmployeeBaseForm):
    """Form used to register a new employee with strict unique checks."""

    def validate_employee_id(self, field):
        cleaned_id = field.data.strip().upper()
        existing = Employee.query.filter(
            func.upper(Employee.employee_id) == cleaned_id
        ).first()
        if existing:
            raise ValidationError(f"Employee ID '{cleaned_id}' is already assigned to {existing.full_name}.")

    def validate_email(self, field):
        cleaned_email = field.data.strip().lower()
        existing = Employee.query.filter(
            func.lower(Employee.email) == cleaned_email
        ).first()
        if existing:
            raise ValidationError(f"Email '{cleaned_email}' is already in use by another employee ({existing.full_name}).")


class EmployeeEditForm(EmployeeBaseForm):
    """Form used to update an existing employee, ignoring their own current ID and email."""

    def __init__(self, original_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_id = original_id

    def validate_employee_id(self, field):
        cleaned_id = field.data.strip().upper()
        existing = Employee.query.filter(
            func.upper(Employee.employee_id) == cleaned_id,
            Employee.id != self.original_id,
        ).first()
        if existing:
            raise ValidationError(f"Employee ID '{cleaned_id}' is already assigned to {existing.full_name}.")

    def validate_email(self, field):
        cleaned_email = field.data.strip().lower()
        existing = Employee.query.filter(
            func.lower(Employee.email) == cleaned_email,
            Employee.id != self.original_id,
        ).first()
        if existing:
            raise ValidationError(f"Email '{cleaned_email}' is already in use by {existing.full_name}.")


class EmployeeSearchFilterForm(FlaskForm):
    """Filter and search form for the employee directory."""

    q = StringField(
        "Search",
        validators=[Optional()],
        render_kw={"placeholder": "Search by name, employee ID, or email..."},
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
    )
    job_title = StringField(
        "Job Title",
        validators=[Optional()],
        render_kw={"placeholder": "Filter by job title..."},
    )
    status = SelectField(
        "Status",
        choices=[
            ("", "All Statuses"),
            ("active", "Active"),
            ("on_leave", "On Leave"),
            ("terminated", "Terminated"),
        ],
        default="",
        validators=[Optional()],
    )

