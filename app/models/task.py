"""
Task Model Module.

Tracks company tasks, assignments, priorities, deadlines, and completion statuses.
"""

from datetime import datetime, timezone, date
from app.extensions import db


class Task(db.Model):
    """Corporate task assignment and status tracking entity."""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    priority = db.Column(db.String(20), default="medium", nullable=False)  # low, medium, high, urgent
    status = db.Column(db.String(20), default="pending", nullable=False)    # pending, in_progress, completed, cancelled
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    assignee = db.relationship("Employee", back_populates="tasks")
    creator = db.relationship("User", foreign_keys=[created_by_id])

    PRIORITIES = ("low", "medium", "high", "urgent")
    STATUSES = ("pending", "in_progress", "completed", "cancelled")

    @property
    def is_overdue(self) -> bool:
        """Returns True if the task has passed its due date and is not completed/cancelled."""
        if not self.due_date:
            return False
        return self.due_date < date.today() and self.status not in ("completed", "cancelled")

    @property
    def priority_badge_class(self) -> str:
        """Returns Bootstrap badge CSS class based on priority level."""
        mapping = {
            "urgent": "bg-danger text-white",
            "high": "bg-warning text-dark border border-warning",
            "medium": "bg-primary-subtle text-primary border border-primary-subtle",
            "low": "bg-secondary-subtle text-secondary border",
        }
        return mapping.get(self.priority, "bg-secondary text-white")

    @property
    def status_badge_class(self) -> str:
        """Returns Bootstrap badge CSS class based on completion status."""
        mapping = {
            "completed": "bg-success-subtle text-success border border-success-subtle",
            "in_progress": "bg-info-subtle text-info border border-info-subtle",
            "pending": "bg-warning-subtle text-warning-emphasis border border-warning-subtle",
            "cancelled": "bg-secondary-subtle text-secondary border",
        }
        return mapping.get(self.status, "bg-secondary text-white")

    def mark_completed(self) -> None:
        """Updates status to completed with UTC timestamp."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)

    def mark_in_progress(self) -> None:
        """Updates status to in_progress."""
        self.status = "in_progress"
        self.completed_at = None

    def mark_pending(self) -> None:
        """Resets status to pending."""
        self.status = "pending"
        self.completed_at = None

    def __repr__(self) -> str:
        return f"<Task #{self.id} '{self.title}' [{self.status}]>"
