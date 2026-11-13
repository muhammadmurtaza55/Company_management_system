"""
Leave Request Model Module.

Tracks employee leave submissions, vacation, sick days, approval workflows,
and review history.
"""

from datetime import datetime, timezone, date
from app.extensions import db


class LeaveRequest(db.Model):
    """Leave request entity submitted by employees and approved by managers/admin."""
    __tablename__ = "leave_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type = db.Column(db.String(50), nullable=False)  # annual, sick, casual, maternity, unpaid, emergency
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)  # pending, approved, rejected, cancelled

    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = db.Column(db.DateTime, nullable=True)
    review_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    employee = db.relationship("Employee", back_populates="leave_requests")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_id])

    LEAVE_TYPES = [
        ("annual", "Annual / Vacation Leave"),
        ("sick", "Sick Leave"),
        ("casual", "Casual Leave"),
        ("emergency", "Emergency Leave"),
        ("maternity", "Maternity / Paternity Leave"),
        ("unpaid", "Unpaid Leave"),
    ]

    STATUSES = ("pending", "approved", "rejected", "cancelled")

    @property
    def duration_days(self) -> int:
        """Returns inclusive duration in calendar days."""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0

    @property
    def is_pending(self) -> bool:
        return self.status == "pending"

    @property
    def is_approved(self) -> bool:
        return self.status == "approved"

    @property
    def is_rejected(self) -> bool:
        return self.status == "rejected"

    def __repr__(self) -> str:
        return f"<LeaveRequest #{self.id} Emp #{self.employee_id} [{self.leave_type}] {self.status}>"

