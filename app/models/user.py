"""
User Model Module.

Integrates with Flask-Login and Werkzeug for secure password hashing and role-based access.
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


class User(UserMixin, db.Model):
    """User account model for authentication and system permissions."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="employee", nullable=False)  # admin, manager, employee
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # 1-to-1 Relationship with Employee profile
    employee = db.relationship("Employee", back_populates="user", uselist=False, cascade="all, delete-orphan")

    ROLES = ("admin", "manager", "employee")

    def set_password(self, password: str) -> None:
        """Hashes the password securely."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifies the password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role == "manager"

    @property
    def is_employee(self) -> bool:
        return self.role == "employee"

    def has_role(self, *roles: str) -> bool:
        """Checks if user has any of the specified roles."""
        return self.role in roles

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"

