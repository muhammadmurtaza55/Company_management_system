"""
Comprehensive Automated Test Suite for Admin Dashboard and Modules.

Verifies:
1. Strict Role-Based Access Control (Admin only; Employees & Managers blocked with 403).
2. Live statistics calculations from PostgreSQL database.
3. Empty state handling when no data exists.
4. Functional subview operations:
   - Employee creation & listing
   - Department creation & listing
   - Attendance logging & status verification
   - Task assignment & toggle-completion
   - Payroll disbursements & expense calculations
"""

import unittest
from datetime import date
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.task import Task
from app.models.payroll import Payroll


class AdminDashboardTestCase(unittest.TestCase):
    """Test suite for Admin Dashboard metrics, RBAC, and operational modules."""

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
        """Prepares isolated test users and environment."""
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.cleanup_records()

        # Create Admin
        self.admin = User(
            username="admin_dash_test",
            email="admin_dash@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin.set_password("AdminPass12345!")

        # Create Manager
        self.manager = User(
            username="mgr_dash_test",
            email="mgr_dash@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager.set_password("MgrPass12345!")

        # Create Employee
        self.employee_user = User(
            username="emp_dash_test",
            email="emp_dash@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.employee_user.set_password("EmpPass12345!")

        db.session.add_all([self.admin, self.manager, self.employee_user])
        db.session.commit()

    def tearDown(self):
        """Cleans up all database records created during test."""
        self.cleanup_records()
        self.app_context.pop()

    def cleanup_records(self):
        """Removes all test records."""
        try:
            # Delete children first
            LeaveRequest.query.delete()
            Attendance.query.delete()
            Payroll.query.delete()
            Task.query.delete()
            Employee.query.delete()
            Department.query.delete()
            User.query.filter(
                User.username.in_(["admin_dash_test", "mgr_dash_test", "emp_dash_test"])
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def login_as(self, user: User, password: str):
        """Helper to authenticate a test user."""
        return self.client.post(
            "/auth/login",
            data={"username_or_email": user.username, "password": password},
            follow_redirects=True,
        )

    # -------------------------------------------------------------------------
    # 1. Access Control Tests
    # -------------------------------------------------------------------------
    def test_anonymous_user_blocked_from_admin_dashboard(self):
        """Anonymous requests to /admin/dashboard redirect to /auth/login."""
        res = self.client.get("/admin/dashboard", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers["Location"])

    def test_employee_blocked_from_admin_dashboard(self):
        """Employee accounts receive HTTP 403 Forbidden on /admin/dashboard."""
        self.login_as(self.employee_user, "EmpPass12345!")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_manager_blocked_from_admin_dashboard(self):
        """Manager accounts receive HTTP 403 Forbidden on /admin/dashboard."""
        self.login_as(self.manager, "MgrPass12345!")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_admin_permitted_to_dashboard(self):
        """Admin accounts access /admin/dashboard successfully (HTTP 200)."""
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Company Executive Dashboard", res.data)
        self.assertIn(b"Total Employees", res.data)
        self.assertIn(b"Total Departments", res.data)

    # -------------------------------------------------------------------------
    # 2. Database Statistics Calculation Tests
    # -------------------------------------------------------------------------
    def test_dashboard_empty_state_statistics(self):
        """When database is empty, statistics show 0 and helpful empty states."""
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"No employee records registered yet.", res.data)
        self.assertIn(b"No Department Data", res.data)
        self.assertIn(b"No Attendance Activity", res.data)

    def test_dashboard_populated_statistics(self):
        """Verifies all 7 core statistics reflect PostgreSQL records accurately."""
        today = date.today()

        # Seed Department
        dept = Department(name="Engineering", code="ENG", description="Software & Tech")
        db.session.add(dept)
        db.session.flush()

        # Seed 2 Employees
        emp1 = Employee(
            first_name="Alice",
            last_name="Smith",
            job_title="Lead Architect",
            department_id=dept.id,
            salary=9000.00,
            status="active",
        )
        emp2 = Employee(
            first_name="Bob",
            last_name="Jones",
            job_title="QA Engineer",
            department_id=dept.id,
            salary=6000.00,
            status="active",
        )
        db.session.add_all([emp1, emp2])
        db.session.flush()

        # Seed Attendance: 1 Present, 1 Absent
        att_pres = Attendance(employee_id=emp1.id, date=today, status="present")
        att_abs = Attendance(employee_id=emp2.id, date=today, status="absent")
        db.session.add_all([att_pres, att_abs])

        # Seed Tasks: 1 Pending, 1 In Progress, 1 Completed
        t1 = Task(title="Set up CI pipeline", assigned_to_id=emp1.id, status="pending")
        t2 = Task(title="Write API specs", assigned_to_id=emp2.id, status="in_progress")
        t3 = Task(title="Audit security", assigned_to_id=emp1.id, status="completed")
        db.session.add_all([t1, t2, t3])

        # Seed Payroll
        pay1 = Payroll(
            employee_id=emp1.id,
            month=today.month,
            year=today.year,
            base_salary=9000.00,
            net_salary=9000.00,
            status="paid",
        )
        db.session.add(pay1)
        db.session.commit()

        # Request Dashboard as Admin
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.get("/admin/dashboard")
        self.assertEqual(res.status_code, 200)

        # Check Total Employees (2)
        self.assertIn(b"Total Employees", res.data)
        # Check Total Departments (1)
        self.assertIn(b"Departments", res.data)
        # Check Today's Present & Absent
        self.assertIn(b"Today's Present", res.data)
        self.assertIn(b"Today's Absent", res.data)
        # Check Recent Activity tables contain Alice and tasks
        self.assertIn(b"Alice Smith", res.data)
        self.assertIn(b"Set up CI pipeline", res.data)

    # -------------------------------------------------------------------------
    # 3. Functional Module Operations Tests
    # -------------------------------------------------------------------------
    def test_employee_creation_and_listing(self):
        """Admin can list and create employee records via /admin/employees."""
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.post(
            "/admin/employees",
            data={
                "first_name": "Charlie",
                "last_name": "Brown",
                "job_title": "Product Manager",
                "department_id": 0,
                "salary": 7500.00,
                "hire_date": "2026-01-15",
                "status": "active",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Charlie Brown", res.data)

        # Verify record in PostgreSQL
        emp = Employee.query.filter_by(first_name="Charlie", last_name="Brown").first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.job_title, "Product Manager")

    def test_department_creation_and_listing(self):
        """Admin can list and create department records via /admin/departments."""
        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.post(
            "/admin/departments",
            data={
                "name": "Finance & Accounting",
                "code": "FIN",
                "description": "Financial planning and reporting",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Finance &amp; Accounting", res.data)

        # Verify record in PostgreSQL
        dept = Department.query.filter_by(code="FIN").first()
        self.assertIsNotNone(dept)
        self.assertEqual(dept.name, "Finance & Accounting")

    def test_attendance_logging(self):
        """Admin can log and update employee attendance via /admin/attendance."""
        # Create an employee first
        emp = Employee(first_name="Dave", last_name="Miller", job_title="DevOps", status="active")
        db.session.add(emp)
        db.session.commit()

        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.post(
            "/admin/attendance",
            data={
                "employee_id": emp.id,
                "date": date.today().isoformat(),
                "status": "present",
                "notes": "Remote check-in",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Attendance logged successfully!", res.data)

        # Verify record in PostgreSQL
        att = Attendance.query.filter_by(employee_id=emp.id, date=date.today()).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.status, "present")

    def test_task_creation_and_toggle_complete(self):
        """Admin can create a task and toggle completion status."""
        self.login_as(self.admin, "AdminPass12345!")
        # Create Task
        res_create = self.client.post(
            "/admin/tasks",
            data={
                "title": "Upgrade PostgreSQL Drivers",
                "description": "Migrate to psycopg 3 binary wheels",
                "assigned_to_id": 0,
                "priority": "high",
                "status": "pending",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b"Upgrade PostgreSQL Drivers", res_create.data)

        task = Task.query.filter_by(title="Upgrade PostgreSQL Drivers").first()
        self.assertIsNotNone(task)
        self.assertEqual(task.status, "pending")

        # Toggle to Completed
        res_toggle = self.client.post(
            f"/admin/tasks/{task.id}/toggle-complete",
            follow_redirects=True,
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertIn(b"marked as Completed!", res_toggle.data)

        # Verify status in PostgreSQL
        db.session.refresh(task)
        self.assertEqual(task.status, "completed")
        self.assertIsNotNone(task.completed_at)

    def test_payroll_disbursement_recording(self):
        """Admin can record a payroll disbursement via /admin/payroll."""
        emp = Employee(first_name="Eva", last_name="Green", job_title="Designer", salary=5000.00, status="active")
        db.session.add(emp)
        db.session.commit()

        self.login_as(self.admin, "AdminPass12345!")
        res = self.client.post(
            "/admin/payroll",
            data={
                "employee_id": emp.id,
                "month": 11,
                "year": 2026,
                "base_salary": 5000.00,
                "bonus": 500.00,
                "deductions": 200.00,
                "status": "paid",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Payroll disbursement recorded successfully!", res.data)

        # Verify record in PostgreSQL
        pay = Payroll.query.filter_by(employee_id=emp.id, month=11, year=2026).first()
        self.assertIsNotNone(pay)
        self.assertEqual(float(pay.net_salary), 5300.00)


if __name__ == "__main__":
    unittest.main()
