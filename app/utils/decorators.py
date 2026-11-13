"""
Role-Based Access Control (RBAC) Decorators.

Provides route protection based on user authentication status and corporate roles:
Admin, Manager, and Employee.
"""

from functools import wraps
from flask import abort, current_app
from flask_login import current_user


def role_required(*allowed_roles: str):
    """
    Decorator to restrict route access to users with specific roles.
    
    :param allowed_roles: Roles authorized to access this route (e.g. 'admin', 'manager').
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # If not logged in, delegate to Flask-Login's unauthorized handler
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()

            # Verify user account is active
            if not current_user.is_active:
                abort(403)

            # Check role permission
            if current_user.role not in allowed_roles:
                abort(403)

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Restricts route to Admin users only."""
    return role_required("admin")(f)


def manager_or_admin_required(f):
    """Restricts route to Managers and Admins."""
    return role_required("admin", "manager")(f)

