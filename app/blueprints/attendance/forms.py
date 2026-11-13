"""
Attendance Blueprint Forms.

Provides forms for leave requests, review workflows, manual attendance logging,
and report filtering.
"""

from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DateField,
    TimeField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    Optional,
    Length,
    ValidationError,
)
from app.models.leave_request import LeaveRequest


class LeaveRequestForm(FlaskForm):
    """Employee leave submission form."""

    leave_type = SelectField(
        "Leave Type",
        choices=LeaveRequest.LEAVE_TYPES,
        validators=[DataRequired(message="Please select a leave category.")],
    )
    start_date = DateField(
        "Start Date",
        default=date.today,
        validators=[DataRequired(message="Start date is required.")],
    )
    end_date = DateField(
        "End Date",
        default=date.today,
        validators=[DataRequired(message="End date is required.")],
    )
    reason = TextAreaField(
        "Reason for Leave",
        validators=[
            DataRequired(message="Please provide a brief justification."),
            Length(max=500, message="Reason cannot exceed 500 characters."),
        ],
        render_kw={"placeholder": "State the purpose of your leave request...", "rows": 3},
    )
    submit = SubmitField("Submit Leave Request")

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError("End date cannot be prior to the start date.")


class LeaveReviewForm(FlaskForm):
    """Manager/Admin leave request approval or rejection form."""

    review_notes = TextAreaField(
        "Review Notes / Feedback",
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Optional comments or feedback for the employee...", "rows": 2},
    )


class ManualAttendanceForm(FlaskForm):
    """Admin / Manager manual attendance logging or adjustment form."""

    employee_id = SelectField(
        "Employee",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    date = DateField(
        "Attendance Date",
        default=date.today,
        validators=[DataRequired(message="Date is required.")],
    )
    status = SelectField(
        "Attendance Status",
        choices=[
            ("present", "Present (On Time)"),
            ("late", "Late Arrival"),
            ("half_day", "Half Day"),
            ("absent", "Absent"),
            ("on_leave", "On Approved Leave"),
        ],
        default="present",
        validators=[DataRequired()],
    )
    check_in = TimeField(
        "Check-in Time",
        validators=[Optional()],
    )
    check_out = TimeField(
        "Check-out Time",
        validators=[Optional()],
    )
    notes = StringField(
        "Notes / Explanation",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "e.g. Remote work, approved half day, doctor note"},
    )
    submit = SubmitField("Save Attendance Record")

    def validate_check_out(self, field):
        if self.check_in.data and field.data:
            if field.data < self.check_in.data:
                raise ValidationError("Check-out time must be after check-in time.")


class DailyReportFilterForm(FlaskForm):
    """Form to filter the daily attendance report."""

    date = DateField(
        "Report Date",
        default=date.today,
        validators=[Optional()],
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
    )
    status = SelectField(
        "Status",
        choices=[
            ("", "All Statuses"),
            ("present", "Present"),
            ("late", "Late Arrival"),
            ("absent", "Absent"),
            ("on_leave", "On Leave"),
            ("not_checked_in", "Not Checked In (Pending)"),
        ],
        default="",
        validators=[Optional()],
    )


class MonthlyReportFilterForm(FlaskForm):
    """Form to filter monthly attendance summary reports."""

    month = SelectField(
        "Month",
        coerce=int,
        choices=[
            (1, "January"), (2, "February"), (3, "March"), (4, "April"),
            (5, "May"), (6, "June"), (7, "July"), (8, "August"),
            (9, "September"), (10, "October"), (11, "November"), (12, "December")
        ],
        validators=[Optional()],
    )
    year = SelectField(
        "Year",
        coerce=int,
        choices=[(y, str(y)) for y in range(2023, 2028)],
        validators=[Optional()],
    )
    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()],
    )

