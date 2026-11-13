"""
Authentication Blueprint Routes.

Implements session management, login/logout, password updates, and Admin-only user management.
"""

from datetime import datetime, timezone
from urllib.parse import urlsplit
from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import func
from app.blueprints.auth import auth_bp
from app.blueprints.auth.forms import (
    LoginForm,
    AdminCreateUserForm,
    ChangePasswordForm,
    AdminSetupForm,
)
from app.extensions import db
from app.models.user import User
from app.models.employee import Employee
from app.utils.decorators import admin_required


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticates users via username or corporate email with password hashing."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    no_users_exist = (User.query.count() == 0)

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.username_or_email.data.strip()
        user = User.query.filter(
            (func.lower(User.username) == func.lower(identifier))
            | (func.lower(User.email) == func.lower(identifier))
        ).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash(
                    "Your account has been deactivated. Please contact your company administrator.",
                    "danger",
                )
                return render_template("auth/login.html", form=form, no_users_exist=no_users_exist)

            # Successful authentication
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            # Prevent open-redirect vulnerabilities
            next_page = request.args.get("next")
            if not next_page or urlsplit(next_page).netloc != "":
                next_page = url_for("main.index")

            flash(f"Welcome back, {user.username}! Signed in as {user.role.title()}.", "success")
            return redirect(next_page)

        flash("Invalid credentials. Please verify your username/email and password.", "danger")

    return render_template("auth/login.html", form=form, no_users_exist=no_users_exist)


@auth_bp.route("/logout")
@login_required
def logout():
    """Terminates the user session."""
    logout_user()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Displays current user profile information and allows password modification."""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Your password has been updated successfully!", "success")
            return redirect(url_for("auth.profile"))

    return render_template("auth/profile.html", form=form)


@auth_bp.route("/users")
@login_required
@admin_required
def list_users():
    """Admin-only: Lists all registered corporate user accounts."""
    users = User.query.order_by(User.id.asc()).all()
    return render_template("auth/users.html", users=users)


@auth_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    """Admin-only: Provisions a new user account with role-based access."""
    form = AdminCreateUserForm()

    if form.validate_on_submit():
        new_user = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            is_active=form.is_active.data,
        )
        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.flush()

        # Optionally link an employee profile if names were provided
        if form.first_name.data or form.last_name.data:
            employee_profile = Employee(
                user_id=new_user.id,
                first_name=form.first_name.data.strip() if form.first_name.data else form.username.data.strip(),
                last_name=form.last_name.data.strip() if form.last_name.data else "",
                job_title=form.job_title.data.strip() if form.job_title.data else f"{form.role.title()}",
            )
            db.session.add(employee_profile)

        db.session.commit()
        flash(
            f"User account '{new_user.username}' created successfully with role '{new_user.role.title()}'!",
            "success",
        )
        return redirect(url_for("auth.list_users"))

    return render_template("auth/create_user.html", form=form)


@auth_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@admin_required
def toggle_user_status(user_id: int):
    """Admin-only: Activates or deactivates a user account."""
    if user_id == current_user.id:
        flash("You cannot deactivate your own administrative account.", "warning")
        return redirect(url_for("auth.list_users"))

    target_user = User.query.get_or_404(user_id)
    target_user.is_active = not target_user.is_active
    db.session.commit()

    status_str = "activated" if target_user.is_active else "deactivated"
    flash(f"User account '{target_user.username}' has been {status_str} successfully.", "success")
    return redirect(url_for("auth.list_users"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    Initial Administrator setup or public registration gate.
    If no users exist in PostgreSQL, allows provisioning the initial Admin directly.
    Once an admin exists, public self-registration is closed.
    """
    # Check if database has zero users
    if User.query.count() == 0:
        form = AdminSetupForm()
        if form.validate_on_submit():
            admin_user = User(
                username=form.username.data.strip(),
                email=form.email.data.strip().lower(),
                role="admin",
                is_active=True,
            )
            admin_user.set_password(form.password.data)
            db.session.add(admin_user)
            db.session.commit()

            # Automatically sign in the new administrator
            login_user(admin_user)
            flash(
                f"Initial Administrator account '{admin_user.username}' created successfully! Welcome to the Admin Dashboard.",
                "success",
            )
            return redirect(url_for("admin.dashboard"))

        return render_template("auth/setup_admin.html", form=form)

    if current_user.is_authenticated and current_user.is_admin:
        return redirect(url_for("auth.create_user"))

    flash(
        "Public self-registration is disabled for enterprise security. Please contact an administrator to provision your account.",
        "warning",
    )
    return redirect(url_for("auth.login"))
