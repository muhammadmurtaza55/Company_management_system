"""
Authentication and User Management Forms.

Utilizes Flask-WTF and WTForms with robust validation and CSRF protection.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp, Optional, ValidationError
from sqlalchemy import func
from app.models.user import User


class AdminSetupForm(FlaskForm):
    """Initial Administrator setup form when database has zero registered users."""
    username = StringField(
        "Administrator Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=3, max=64, message="Username must be between 3 and 64 characters."),
            Regexp(
                r"^[a-zA-Z0-9_.-]+$",
                message="Username may only contain letters, numbers, underscores, dots, or hyphens.",
            ),
        ],
        default="admin",
        render_kw={"placeholder": "e.g. admin", "autofocus": True},
    )
    email = StringField(
        "Corporate Email",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
            Length(max=120),
        ],
        default="admin@company.com",
        render_kw={"placeholder": "e.g. admin@company.com"},
    )
    password = PasswordField(
        "Admin Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long."),
        ],
        render_kw={"placeholder": "Minimum 8 characters", "id": "adminPassword"},
    )
    confirm_password = PasswordField(
        "Confirm Admin Password",
        validators=[
            DataRequired(message="Please confirm the password."),
            EqualTo("password", message="Passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter password", "id": "adminConfirmPassword"},
    )
    submit = SubmitField("Initialize Administrator Account")


class LoginForm(FlaskForm):
    """User Sign-in form supporting login by username or email."""
    username_or_email = StringField(
        "Username or Email",
        validators=[
            DataRequired(message="Please enter your username or email address."),
            Length(max=120),
        ],
        render_kw={"placeholder": "e.g. admin or employee@company.com", "autofocus": True},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired(message="Please enter your password.")],
        render_kw={"placeholder": "Enter your password"},
    )
    remember_me = BooleanField("Remember this device for 30 days")
    submit = SubmitField("Sign In")


class AdminCreateUserForm(FlaskForm):
    """Admin-only form to provision new user accounts with designated roles."""
    username = StringField(
        "Username",
        validators=[
            DataRequired(message="Username is required."),
            Length(min=3, max=64, message="Username must be between 3 and 64 characters."),
            Regexp(
                r"^[a-zA-Z0-9_.-]+$",
                message="Username may only contain letters, numbers, underscores, dots, or hyphens.",
            ),
        ],
        render_kw={"placeholder": "e.g. jdoe"},
    )
    email = StringField(
        "Corporate Email",
        validators=[
            DataRequired(message="Email address is required."),
            Email(message="Please enter a valid email address."),
            Length(max=120),
        ],
        render_kw={"placeholder": "e.g. jdoe@company.com"},
    )
    role = SelectField(
        "Role & Permissions",
        choices=[
            ("employee", "Employee - Standard staff access"),
            ("manager", "Manager - Departmental & team management"),
            ("admin", "Admin - Full system & user administration"),
        ],
        default="employee",
        validators=[DataRequired(message="Please select a user role.")],
    )
    password = PasswordField(
        "Initial Password",
        validators=[
            DataRequired(message="Password is required."),
            Length(min=8, message="Password must be at least 8 characters long."),
        ],
        render_kw={"placeholder": "Minimum 8 characters"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(message="Please confirm the password."),
            EqualTo("password", message="Passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter password"},
    )
    is_active = BooleanField("Account Active", default=True)

    # Optional Employee Profile Association
    first_name = StringField("First Name", validators=[Optional(), Length(max=64)])
    last_name = StringField("Last Name", validators=[Optional(), Length(max=64)])
    job_title = StringField("Job Title", validators=[Optional(), Length(max=100)])

    submit = SubmitField("Create User Account")

    def validate_username(self, field):
        """Ensures the username is unique in PostgreSQL."""
        existing = User.query.filter(func.lower(User.username) == func.lower(field.data.strip())).first()
        if existing:
            raise ValidationError(f"Username '{field.data}' is already registered. Please choose another.")

    def validate_email(self, field):
        """Ensures the email address is unique in PostgreSQL."""
        existing = User.query.filter(func.lower(User.email) == func.lower(field.data.strip())).first()
        if existing:
            raise ValidationError(f"Email '{field.data}' is already associated with an account.")


class ChangePasswordForm(FlaskForm):
    """Authenticated user password modification form."""
    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired(message="Current password is required.")],
        render_kw={"placeholder": "Enter your current password"},
    )
    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(message="New password is required."),
            Length(min=8, message="New password must be at least 8 characters long."),
        ],
        render_kw={"placeholder": "Minimum 8 characters"},
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(message="Please confirm your new password."),
            EqualTo("new_password", message="New passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter new password"},
    )
    submit = SubmitField("Update Password")

