"""
Payroll Blueprint Forms.

Form definitions for:
- Creating and editing individual payroll records.
- Batch generating monthly payroll for all active staff.
- Setting/updating employee basic salary.
- Filtering and searching salary histories.
"""

from calendar import month_name
from datetime import date
from flask_wtf import FlaskForm
from wtforms import (
    SelectField,
    DecimalField,
    IntegerField,
    StringField,
    TextAreaField,
    DateField,
    BooleanField,
    SubmitField,
)
from wtforms.validators import (
    DataRequired,
    InputRequired,
    NumberRange,
    Length,
    Optional,
)


MONTH_CHOICES = [(m, month_name[m]) for m in range(1, 13)]

PAYMENT_METHODS = [
    ("Bank Transfer", "Bank Transfer (Direct Deposit)"),
    ("Direct Deposit", "Direct Deposit"),
    ("Cheque", "Company Cheque"),
    ("Cash", "Cash Disbursement"),
    ("Other", "Other / Electronic Wire"),
]

STATUS_CHOICES = [
    ("paid", "Paid (Disbursed)"),
    ("pending", "Pending (Approved / Unpaid)"),
    ("processing", "Processing (In Review)"),
]


class PayrollRecordForm(FlaskForm):
    """Form for logging or editing individual employee monthly compensation."""

    employee_id = SelectField(
        "Employee",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    month = SelectField(
        "Pay Month",
        coerce=int,
        choices=MONTH_CHOICES,
        default=date.today().month,
        validators=[DataRequired()],
    )
    year = IntegerField(
        "Pay Year",
        default=date.today().year,
        validators=[
            DataRequired(),
            NumberRange(min=2020, max=2050, message="Year must be between 2020 and 2050."),
        ],
    )
    base_salary = DecimalField(
        "Basic Salary ($)",
        places=2,
        validators=[
            InputRequired(message="Basic salary is required."),
            NumberRange(min=0, message="Basic salary cannot be negative."),
        ],
    )
    bonus = DecimalField(
        "Bonus ($)",
        places=2,
        default=0.00,
        validators=[
            InputRequired(message="Bonus is required (use 0 if none)."),
            NumberRange(min=0, message="Bonus cannot be negative."),
        ],
    )
    bonus_description = StringField(
        "Bonus Reason / Type",
        validators=[Optional(), Length(max=255)],
    )
    deductions = DecimalField(
        "Deductions ($)",
        places=2,
        default=0.00,
        validators=[
            InputRequired(message="Deductions amount is required (use 0 if none)."),
            NumberRange(min=0, message="Deductions cannot be negative."),
        ],
    )
    deduction_description = StringField(
        "Deduction Reason / Type",
        validators=[Optional(), Length(max=255)],
    )
    payment_date = DateField(
        "Payment Date",
        default=date.today,
        validators=[Optional()],
    )
    payment_method = SelectField(
        "Payment Method",
        choices=PAYMENT_METHODS,
        default="Bank Transfer",
        validators=[DataRequired()],
    )
    reference_no = StringField(
        "Transaction / Cheque Reference",
        validators=[Optional(), Length(max=100)],
    )
    status = SelectField(
        "Disbursement Status",
        choices=STATUS_CHOICES,
        default="paid",
        validators=[DataRequired()],
    )
    notes = TextAreaField(
        "Internal Administrative Notes",
        validators=[Optional(), Length(max=1000)],
    )
    submit = SubmitField("Save Payroll Record")


class BatchPayrollGenerateForm(FlaskForm):
    """Form to generate monthly payroll records in bulk for all active employees."""

    month = SelectField(
        "Pay Month",
        coerce=int,
        choices=MONTH_CHOICES,
        default=date.today().month,
        validators=[DataRequired()],
    )
    year = IntegerField(
        "Pay Year",
        default=date.today().year,
        validators=[
            DataRequired(),
            NumberRange(min=2020, max=2050, message="Year must be between 2020 and 2050."),
        ],
    )
    department_id = SelectField(
        "Target Department",
        coerce=int,
        default=0,
        validators=[Optional()],
    )
    payment_date = DateField(
        "Payment Date",
        default=date.today,
        validators=[Optional()],
    )
    payment_method = SelectField(
        "Payment Method",
        choices=PAYMENT_METHODS,
        default="Bank Transfer",
        validators=[DataRequired()],
    )
    status = SelectField(
        "Initial Status",
        choices=STATUS_CHOICES,
        default="paid",
        validators=[DataRequired()],
    )
    overwrite_existing = BooleanField(
        "Update basic salary on existing records if already generated",
        default=False,
    )
    submit = SubmitField("Run Batch Payroll Generation")


class UpdateBaseSalaryForm(FlaskForm):
    """Form for setting or adjusting an employee's structural basic salary."""

    employee_id = SelectField(
        "Select Employee",
        coerce=int,
        validators=[DataRequired(message="Please select an employee.")],
    )
    new_salary = DecimalField(
        "New Basic Monthly Salary ($)",
        places=2,
        validators=[
            InputRequired(message="Basic salary is required."),
            NumberRange(min=0, message="Basic salary cannot be negative."),
        ],
    )
    effective_date = DateField(
        "Effective Date",
        default=date.today,
        validators=[Optional()],
    )
    reason = StringField(
        "Adjustment Justification",
        validators=[Optional(), Length(max=255)],
    )
    submit = SubmitField("Update Basic Salary")


class PayrollSearchFilterForm(FlaskForm):
    """Search and filter form for salary history table."""

    search = StringField("Search Employee", validators=[Optional()])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    month = SelectField("Month", coerce=int, validators=[Optional()])
    year = SelectField("Year", coerce=int, validators=[Optional()])
    status = SelectField("Status", validators=[Optional()])

