"""
Attendance Model Module.

Tracks daily employee attendance, check-in/out times, late arrival tracking,
and attendance statuses against PostgreSQL.
"""

from datetime import datetime, timezone, date, time, timedelta
from app.extensions import db


class Attendance(db.Model):
    """Daily attendance record for company employees."""
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    status = db.Column(db.String(20), default="present", nullable=False, index=True)  # present, absent, late, half_day, on_leave
    check_in = db.Column(db.Time, nullable=True)
    check_out = db.Column(db.Time, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Standard expected arrival threshold (9:30 AM)
    STANDARD_START_TIME = time(9, 30, 0)

    # Relationships
    employee = db.relationship("Employee", back_populates="attendances")

    __table_args__ = (
        db.UniqueConstraint("employee_id", "date", name="uq_employee_attendance_date"),
    )

    @property
    def is_late(self) -> bool:
        """Determines if the attendance was marked late or check-in was after 9:30 AM."""
        if self.status == "late":
            return True
        if self.check_in and self.check_in > self.STANDARD_START_TIME:
            return True
        return False

    @property
    def minutes_late(self) -> int:
        """Calculates minutes late relative to standard 9:30 AM start."""
        if not self.check_in or self.check_in <= self.STANDARD_START_TIME:
            return 0
        diff_minutes = (self.check_in.hour * 60 + self.check_in.minute) - (
            self.STANDARD_START_TIME.hour * 60 + self.STANDARD_START_TIME.minute
        )
        return max(0, diff_minutes)

    @property
    def work_duration_seconds(self) -> int:
        """Returns worked duration in seconds if both check-in and check-out exist."""
        if not self.check_in or not self.check_out:
            return 0
        t_in = timedelta(hours=self.check_in.hour, minutes=self.check_in.minute, seconds=self.check_in.second)
        t_out = timedelta(hours=self.check_out.hour, minutes=self.check_out.minute, seconds=self.check_out.second)
        if t_out > t_in:
            return int((t_out - t_in).total_seconds())
        return 0

    @property
    def work_duration_formatted(self) -> str:
        """Returns human-readable working hours (e.g. '8 hrs 15 mins')."""
        seconds = self.work_duration_seconds
        if seconds <= 0:
            return "--"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        return f"{minutes}m"

    def __repr__(self) -> str:
        return f"<Attendance Emp #{self.employee_id} on {self.date}: {self.status}>"
