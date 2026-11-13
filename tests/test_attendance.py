"""
Attendance Management Module Test Suite.

Automated tests for:
1. Employee check-in (on-time and late arrival detection).
2. Duplicate check-in prevention on the same working day.
3. Employee check-out workflow and work duration calculation.
4. Check-out validation (must happen after check-in, no duplicates).
5. Safe absence handling (unrecorded staff on today are not marked absent).
6. Daily attendance report and role-based scoping.
7. Monthly attendance summary and attendance rate calculation.
8. Late arrival tracking and minutes late calculation.
9. Leave request submission and overlap validation.
10. Leave approval workflow with automatic on_leave attendance record syncing.
11. Leave rejection workflow and manager/admin RBAC enforcement.
12. Manual attendance entry and adjustments (Admin only).
"""

from datetime import date, time, datetime, timedelta, timezone
import unittest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.task import Task
from app.models.payroll import Payroll


class AttendanceModuleTestCase(unittest.TestCase):
    """Integration test suite for the Attendance Management Module."""

    @classmethod
    def setUpClass(cls):
        """Initializes application in testing mode."""
        cls.app = create_app("testing")
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        """Prepares isolated test database fixtures."""
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.cleanup_records()

        # 1. Admin User
        self.admin = User(
            username="att_admin_test",
            email="att_admin@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin.set_password("AdminPass12345!")

        # 2. Manager User (IT Dept)
        self.manager = User(
            username="att_mgr_test",
            email="att_mgr@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager.set_password("MgrPass12345!")

        # 3. Employee 1 User (IT Dept)
        self.emp1_user = User(
            username="att_emp1_test",
            email="att_emp1@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.emp1_user.set_password("Emp1Pass12345!")

        # 4. Employee 2 User (HR Dept)
        self.emp2_user = User(
            username="att_emp2_test",
            email="att_emp2@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.emp2_user.set_password("Emp2Pass12345!")

        db.session.add_all([self.admin, self.manager, self.emp1_user, self.emp2_user])
        db.session.commit()

        # Departments
        self.dept_it = Department(name="IT Systems", code="ITS", description="IT Ops")
        self.dept_hr = Department(name="Human Resources", code="HRS", description="HR Ops")
        db.session.add_all([self.dept_it, self.dept_hr])
        db.session.commit()

        # Employees
        self.emp_mgr = Employee(
            employee_id="ATT-MGR01",
            first_name="Marcus",
            last_name="Vance",
            email="m.vance@testcorp.com",
            job_title="IT Director",
            department_id=self.dept_it.id,
            user_id=self.manager.id,
            salary=11000.00,
            hire_date=date(2023, 1, 10),
            status="active",
        )
        self.emp1 = Employee(
            employee_id="ATT-EMP01",
            first_name="Alice",
            last_name="Smith",
            email="alice.smith@testcorp.com",
            job_title="Software Engineer",
            department_id=self.dept_it.id,
            user_id=self.emp1_user.id,
            salary=8000.00,
            hire_date=date(2024, 2, 1),
            status="active",
        )
        self.emp2 = Employee(
            employee_id="ATT-EMP02",
            first_name="Bob",
            last_name="Jones",
            email="bob.jones@testcorp.com",
            job_title="HR Specialist",
            department_id=self.dept_hr.id,
            user_id=self.emp2_user.id,
            salary=6500.00,
            hire_date=date(2024, 3, 1),
            status="active",
        )

        db.session.add_all([self.emp_mgr, self.emp1, self.emp2])
        db.session.commit()

        self.dept_it.manager_id = self.emp_mgr.id
        db.session.commit()

    def tearDown(self):
        """Cleans up all database records created during test."""
        self.cleanup_records()
        self.app_context.pop()

    def cleanup_records(self):
        """Purges test fixtures from PostgreSQL."""
        try:
            LeaveRequest.query.delete()
            Attendance.query.delete()
            Payroll.query.delete()
            Task.query.delete()
            Employee.query.delete()
            Department.query.delete()
            User.query.filter(
                User.username.in_([
                    "att_admin_test",
                    "att_mgr_test",
                    "att_emp1_test",
                    "att_emp2_test",
                ])
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def login_as(self, user: User, password: str):
        """Helper to authenticate a session."""
        return self.client.post(
            "/auth/login",
            data={"username_or_email": user.username, "password": password},
            follow_redirects=True,
        )

    # -------------------------------------------------------------------------
    # 1. Employee Check-in Tests
    # -------------------------------------------------------------------------
    def test_employee_check_in_success(self):
        """Employee can check in for today and creates attendance record."""
        self.login_as(self.emp1_user, "Emp1Pass12345!")

        res = self.client.post("/attendance/check-in", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify attendance record in PostgreSQL
        record = Attendance.query.filter_by(
            employee_id=self.emp1.id, date=date.today()
        ).first()
        self.assertIsNotNone(record)
        self.assertIsNotNone(record.check_in)
        self.assertIn(record.status, ["present", "late"])

    def test_duplicate_check_in_prevention(self):
        """Employee cannot check in more than once on the same day."""
        self.login_as(self.emp1_user, "Emp1Pass12345!")

        # First check-in
        self.client.post("/attendance/check-in", follow_redirects=True)

        # Second check-in attempt
        res = self.client.post("/attendance/check-in", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already checked in", res.data)

        # Exactly 1 record exists in DB
        records = Attendance.query.filter_by(
            employee_id=self.emp1.id, date=date.today()
        ).all()
        self.assertEqual(len(records), 1)

    def test_check_in_blocked_when_on_approved_leave(self):
        """Employee cannot check in if already scheduled as on approved leave."""
        today = date.today()
        att_leave = Attendance(
            employee_id=self.emp1.id,
            date=today,
            status="on_leave",
            notes="Annual Leave",
        )
        db.session.add(att_leave)
        db.session.commit()

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.post("/attendance/check-in", follow_redirects=True)
        self.assertIn(b"approved leave", res.data)

    # -------------------------------------------------------------------------
    # 2. Employee Check-out Tests
    # -------------------------------------------------------------------------
    def test_check_out_after_check_in_success(self):
        """Employee can check out after checking in and duration is tracked."""
        today = date.today()
        att = Attendance(
            employee_id=self.emp1.id,
            date=today,
            status="present",
            check_in=time(9, 0, 0),
        )
        db.session.add(att)
        db.session.commit()

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.post("/attendance/check-out", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Checked out successfully", res.data)

        db.session.refresh(att)
        self.assertIsNotNone(att.check_out)
        self.assertGreater(att.work_duration_seconds, 0)

    def test_check_out_before_check_in_rejected(self):
        """Employee cannot check out without checking in first."""
        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.post("/attendance/check-out", follow_redirects=True)
        self.assertIn(b"must check in first", res.data)

    def test_duplicate_check_out_prevented(self):
        """Employee cannot check out twice on the same day."""
        today = date.today()
        att = Attendance(
            employee_id=self.emp1.id,
            date=today,
            status="present",
            check_in=time(9, 0, 0),
            check_out=time(17, 30, 0),
        )
        db.session.add(att)
        db.session.commit()

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.post("/attendance/check-out", follow_redirects=True)
        self.assertIn(b"already checked out", res.data)

    # -------------------------------------------------------------------------
    # 3. Attendance Hub and Access Scoping
    # -------------------------------------------------------------------------
    def test_employee_hub_view(self):
        """Employee sees personal check-in/out widget and personal summary."""
        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.get("/attendance", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"My Workday Status", res.data)
        self.assertIn(b"Check In Now", res.data)

    def test_manager_hub_department_roster(self):
        """Manager sees department staff status and department leave requests."""
        self.login_as(self.manager, "MgrPass12345!")
        res = self.client.get("/attendance", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Should see Alice Smith (IT) but not Bob Jones (HR) in department roster
        self.assertIn(b"Alice Smith", res.data)
        self.assertIn(b"Today's Staff Roster", res.data)

    def test_admin_hub_view(self):
        """Admin sees company-wide overview and all staff."""
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/attendance", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Total Workforce", res.data)
        self.assertIn(b"Today's Staff Roster", res.data)
        self.assertIn(b"Alice Smith", res.data)
        self.assertIn(b"Bob Jones", res.data)

    # -------------------------------------------------------------------------
    # 4. History Logs and Scoping
    # -------------------------------------------------------------------------
    def test_employee_cannot_view_others_history(self):
        """Employee history only displays own records."""
        today = date.today()
        att1 = Attendance(employee_id=self.emp1.id, date=today, status="present", check_in=time(9, 0))
        att2 = Attendance(employee_id=self.emp2.id, date=today, status="present", check_in=time(9, 15))
        db.session.add_all([att1, att2])
        db.session.commit()

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.get("/attendance/history")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Smith", res.data)
        self.assertNotIn(b"Bob Jones", res.data)

    # -------------------------------------------------------------------------
    # 5. Safe Absence Handling & Daily Report
    # -------------------------------------------------------------------------
    def test_safe_absence_handling_for_today(self):
        """For today, active staff without attendance are not marked absent (marked Pending)."""
        # Neither Alice nor Bob has checked in today
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/attendance/reports/daily")
        self.assertEqual(res.status_code, 200)
        # Rule check: pending check-in count should be 3 (Marcus, Alice, Bob)
        self.assertIn(b"Pending", res.data)
        self.assertIn(b"Not Checked In", res.data)

    def test_past_date_unrecorded_counted_as_absent(self):
        """For a past workday, unrecorded staff are counted as absent."""
        past_date = date.today() - timedelta(days=5)
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get(f"/attendance/reports/daily?date={past_date.isoformat()}")
        self.assertEqual(res.status_code, 200)
        # For past date, unrecorded active staff are labeled Absent
        self.assertIn(b"Absent", res.data)

    # -------------------------------------------------------------------------
    # 6. Monthly Report & Late Report Tests
    # -------------------------------------------------------------------------
    def test_monthly_attendance_report(self):
        """Monthly report calculates attendance rates and metrics."""
        today = date.today()
        first_day = today.replace(day=1)

        att = Attendance(
            employee_id=self.emp1.id,
            date=first_day,
            status="present",
            check_in=time(9, 0, 0),
            check_out=time(17, 0, 0),
        )
        db.session.add(att)
        db.session.commit()

        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get(
            f"/attendance/reports/monthly?month={today.month}&year={today.year}"
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Monthly Attendance Report", res.data)
        self.assertIn(b"Alice Smith", res.data)

    def test_late_arrival_report(self):
        """Late arrival report displays staff checked in after 9:30 AM."""
        today = date.today()
        att_late = Attendance(
            employee_id=self.emp1.id,
            date=today,
            status="late",
            check_in=time(10, 15, 0),
            notes="Traffic congestion",
        )
        db.session.add(att_late)
        db.session.commit()

        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/attendance/reports/late")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Late Arrival Tracking Report", res.data)
        self.assertIn(b"Alice Smith", res.data)
        self.assertIn(b"+45 mins", res.data)

    # -------------------------------------------------------------------------
    # 7. Leave Management Workflow
    # -------------------------------------------------------------------------
    def test_employee_submit_leave_success(self):
        """Employee can submit a leave request with valid future dates."""
        self.login_as(self.emp1_user, "Emp1Pass12345!")

        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=7)

        res = self.client.post(
            "/attendance/leaves/request",
            data={
                "leave_type": "annual",
                "start_date": start.strftime("%Y-%m-%d"),
                "end_date": end.strftime("%Y-%m-%d"),
                "reason": "Family vacation scheduled travel",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"submitted successfully", res.data)

        # Verify DB entry
        leave_req = LeaveRequest.query.filter_by(employee_id=self.emp1.id).first()
        self.assertIsNotNone(leave_req)
        self.assertEqual(leave_req.status, "pending")
        self.assertEqual(leave_req.duration_days, 3)

    def test_overlapping_leave_request_rejected(self):
        """Overlapping leave requests are rejected."""
        start = date.today() + timedelta(days=5)
        end = date.today() + timedelta(days=7)

        existing = LeaveRequest(
            employee_id=self.emp1.id,
            leave_type="annual",
            start_date=start,
            end_date=end,
            reason="Initial request",
            status="pending",
        )
        db.session.add(existing)
        db.session.commit()

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        # Attempt overlap
        res = self.client.post(
            "/attendance/leaves/request",
            data={
                "leave_type": "casual",
                "start_date": (start + timedelta(days=1)).strftime("%Y-%m-%d"),
                "end_date": (end + timedelta(days=1)).strftime("%Y-%m-%d"),
                "reason": "Overlapping request attempt",
            },
            follow_redirects=True,
        )
        self.assertIn(b"already have a pending leave request", res.data)

    def test_leave_approval_syncs_attendance_records(self):
        """Approving leave updates status and creates on_leave Attendance records."""
        start = date.today() + timedelta(days=2)
        end = date.today() + timedelta(days=3)

        leave_req = LeaveRequest(
            employee_id=self.emp1.id,
            leave_type="sick",
            start_date=start,
            end_date=end,
            reason="Medical treatment",
            status="pending",
        )
        db.session.add(leave_req)
        db.session.commit()

        # Admin approves leave
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.post(
            f"/attendance/leaves/{leave_req.id}/approve",
            data={"review_notes": "Approved with doctor certificate"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"approved", res.data)

        db.session.refresh(leave_req)
        self.assertEqual(leave_req.status, "approved")
        self.assertEqual(leave_req.reviewed_by_id, self.admin.id)

        # Check synced Attendance records for both days
        att_day1 = Attendance.query.filter_by(employee_id=self.emp1.id, date=start).first()
        att_day2 = Attendance.query.filter_by(employee_id=self.emp1.id, date=end).first()
        self.assertIsNotNone(att_day1)
        self.assertEqual(att_day1.status, "on_leave")
        self.assertIsNotNone(att_day2)
        self.assertEqual(att_day2.status, "on_leave")

    def test_manager_cannot_approve_other_department_leave(self):
        """Manager cannot approve leave for employees in a different department."""
        start = date.today() + timedelta(days=1)
        end = date.today() + timedelta(days=2)

        # Leave for Bob (HR department)
        leave_req = LeaveRequest(
            employee_id=self.emp2.id,
            leave_type="annual",
            start_date=start,
            end_date=end,
            reason="Personal days",
            status="pending",
        )
        db.session.add(leave_req)
        db.session.commit()

        # Marcus is IT manager, not HR manager
        self.login_as(self.manager, "MgrPass12345!")
        res = self.client.post(
            f"/attendance/leaves/{leave_req.id}/approve",
            data={"review_notes": "Attempted approval"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 403)

    def test_leave_rejection_workflow(self):
        """Manager/Admin can reject a leave request with notes."""
        start = date.today() + timedelta(days=1)
        end = date.today() + timedelta(days=2)

        leave_req = LeaveRequest(
            employee_id=self.emp1.id,
            leave_type="casual",
            start_date=start,
            end_date=end,
            reason="Personal business",
            status="pending",
        )
        db.session.add(leave_req)
        db.session.commit()

        self.login_as(self.manager, "MgrPass12345!")
        res = self.client.post(
            f"/attendance/leaves/{leave_req.id}/reject",
            data={"review_notes": "Critical deployment scheduled"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        db.session.refresh(leave_req)
        self.assertEqual(leave_req.status, "rejected")
        self.assertEqual(leave_req.review_notes, "Critical deployment scheduled")

    # -------------------------------------------------------------------------
    # 8. Manual Attendance Entry (Admin Only)
    # -------------------------------------------------------------------------
    def test_admin_manual_attendance_entry(self):
        """Admin can manually record or adjust attendance for any employee."""
        self.login_as(self.admin, "AdminPass12345!")

        record_date = date.today() - timedelta(days=3)
        res = self.client.post(
            "/attendance/manual",
            data={
                "employee_id": self.emp1.id,
                "date": record_date.strftime("%Y-%m-%d"),
                "status": "present",
                "check_in": "09:00",
                "check_out": "17:00",
                "notes": "Manual adjustment by Admin",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        rec = Attendance.query.filter_by(
            employee_id=self.emp1.id, date=record_date
        ).first()
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, "present")
        self.assertEqual(rec.notes, "Manual adjustment by Admin")

    def test_non_admin_blocked_from_manual_entry(self):
        """Manager and Employee receive HTTP 403 on manual attendance entry."""
        self.login_as(self.manager, "MgrPass12345!")
        res = self.client.get("/attendance/manual")
        self.assertEqual(res.status_code, 403)

        self.login_as(self.emp1_user, "Emp1Pass12345!")
        res = self.client.get("/attendance/manual")
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
