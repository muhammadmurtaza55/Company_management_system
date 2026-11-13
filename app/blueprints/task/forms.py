"""
Task Blueprint Forms.

Form definitions for:
- Task creation and assignment.
- Task editing and updating.
- Employee status progression (Pending -> In Progress -> Completed).
- Task search and filtering.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DateField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Optional,
)

PRIORITY_CHOICES = [
    ("low", "Low Priority"),
    ("medium", "Medium Priority"),
    ("high", "High Priority"),
    ("urgent", "Urgent / Critical"),
]

STATUS_CHOICES = [
    ("pending", "Pending"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]


class TaskForm(FlaskForm):
    """Form to create or edit a corporate task."""

    title = StringField(
        "Task Title",
        validators=[
            DataRequired(message="Task title is required."),
            Length(max=150, message="Title must not exceed 150 characters."),
        ],
    )
    description = TextAreaField(
        "Task Description",
        validators=[Optional(), Length(max=2000)],
    )
    assigned_to_id = SelectField(
        "Assignee",
        coerce=int,
        validators=[Optional()],
    )
    priority = SelectField(
        "Priority Level",
        choices=PRIORITY_CHOICES,
        default="medium",
        validators=[DataRequired()],
    )
    status = SelectField(
        "Current Status",
        choices=STATUS_CHOICES,
        default="pending",
        validators=[DataRequired()],
    )
    due_date = DateField(
        "Due Date / Deadline",
        validators=[Optional()],
    )
    submit = SubmitField("Save Task")


class TaskStatusUpdateForm(FlaskForm):
    """Simplified status update form for employees."""

    status = SelectField(
        "Update Status",
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Update Status")

