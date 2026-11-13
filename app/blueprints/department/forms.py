"""
Department Blueprint Forms.

Provides forms with CSRF protection, validation, and dynamic dropdowns
for Department creation, updating, and workforce allocation.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
    ValidationError,
)
from sqlalchemy import func
from app.models.department import Department


class DepartmentBaseForm(FlaskForm):
    """Base form containing common departmental attributes."""

    name = StringField(
        "Department Name",
        validators=[
            DataRequired(message="Department name is required."),
            Length(min=2, max=100, message="Department name must be between 2 and 100 characters."),
        ],
        render_kw={"placeholder": "e.g. Engineering, Human Resources, Finance", "autocomplete": "off"},
    )
    code = StringField(
        "Department Code",
        validators=[
            DataRequired(message="Department code is required."),
            Length(min=2, max=20, message="Department code must be between 2 and 20 characters."),
        ],
        render_kw={"placeholder": "e.g. ENG, HR, FIN, MKT", "autocomplete": "off"},
    )
    description = TextAreaField(
        "Description & Responsibilities",
        validators=[Optional()],
        render_kw={"placeholder": "Brief departmental overview and core functions", "rows": 3},
    )
    manager_id = SelectField(
        "Department Manager / Head of Dept",
        coerce=int,
        validators=[Optional()],
    )
    submit = SubmitField("Save Department")


class DepartmentCreateForm(DepartmentBaseForm):
    """Form to create a new department with unique checks."""

    def validate_name(self, field):
        cleaned = field.data.strip()
        existing = Department.query.filter(
            func.lower(Department.name) == cleaned.lower()
        ).first()
        if existing:
            raise ValidationError(f"A department named '{cleaned}' already exists.")

    def validate_code(self, field):
        cleaned = field.data.strip().upper()
        existing = Department.query.filter(
            func.upper(Department.code) == cleaned
        ).first()
        if existing:
            raise ValidationError(f"Department code '{cleaned}' is already taken.")


class DepartmentEditForm(DepartmentBaseForm):
    """Form to update an existing department, ignoring its own ID."""

    def __init__(self, original_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_id = original_id

    def validate_name(self, field):
        cleaned = field.data.strip()
        existing = Department.query.filter(
            func.lower(Department.name) == cleaned.lower(),
            Department.id != self.original_id,
        ).first()
        if existing:
            raise ValidationError(f"A department named '{cleaned}' already exists.")

    def validate_code(self, field):
        cleaned = field.data.strip().upper()
        existing = Department.query.filter(
            func.upper(Department.code) == cleaned,
            Department.id != self.original_id,
        ).first()
        if existing:
            raise ValidationError(f"Department code '{cleaned}' is already taken.")


class AssignEmployeeForm(FlaskForm):
    """Form to allocate an employee to a department."""

    employee_id = SelectField(
        "Select Employee to Assign",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    submit = SubmitField("Assign to Department")


class DepartmentSearchFilterForm(FlaskForm):
    """Search form for departments."""

    q = StringField(
        "Search",
        validators=[Optional()],
        render_kw={"placeholder": "Search departments by name or code..."},
    )

