"""
Employee Management Module Test Suite.

Automated tests for CRUD operations, validation, search & filtering,
and role-based permissions (Admin, Manager, Employee) against PostgreSQL.
"""

from datetime import date
import unittest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.task import Task
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.payroll import Payroll


class EmployeeModuleTestCase(unittest.TestCase):
    """Integration test suite for the Employee Management Module."""

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

        # Seed Departments
        self.dept_engineering = Department(name="Engineering", code="ENG", description="Software & DevOps")
        self.dept_marketing = Department(name="Marketing", code="MKT", description="Growth & Brand")
        db.session.add_all([self.dept_engineering, self.dept_marketing])
        db.session.commit()

        # 1. Admin User
        self.admin_user = User(
            username="test_admin_emp",
            email="admin_emp@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin_user.set_password("AdminPass12345!")

        # 2. Manager User (Linked to Engineering Department)
        self.manager_user = User(
            username="test_mgr_emp",
            email="mgr_emp@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager_user.set_password("MgrPass12345!")

        # 3. Employee User 1 (Engineering)
        self.employee_user1 = User(
            username="test_emp1",
            email="emp1@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.employee_user1.set_password("EmpPass12345!")

        # 4. Employee User 2 (Marketing)
        self.employee_user2 = User(
            username="test_emp2",
            email="emp2@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.employee_user2.set_password("EmpPass12345!")

        db.session.add_all([self.admin_user, self.manager_user, self.employee_user1, self.employee_user2])
        db.session.commit()

        # Seed Manager Employee Profile
        self.mgr_profile = Employee(
            employee_id="EMP-MGR01",
            first_name="Marcus",
            last_name="Vance",
            email="m.vance@testcorp.com",
            phone="+1-555-0100",
            address="100 Manager Way, Tech City",
            job_title="Engineering Director",
            department_id=self.dept_engineering.id,
            user_id=self.manager_user.id,
            salary=12000.00,
            hire_date=date(2023, 1, 10),
            status="active",
        )

        # Seed Employee 1 (Engineering)
        self.emp1_profile = Employee(
            employee_id="EMP-ENG01",
            first_name="Alice",
            last_name="Johnson",
            email="alice.j@testcorp.com",
            phone="+1-555-0101",
            address="101 Dev Lane, Silicon Valley",
            job_title="Senior Backend Engineer",
            department_id=self.dept_engineering.id,
            user_id=self.employee_user1.id,
            salary=8500.00,
            hire_date=date(2024, 3, 15),
            status="active",
        )

        # Seed Employee 2 (Marketing)
        self.emp2_profile = Employee(
            employee_id="EMP-MKT01",
            first_name="Bob",
            last_name="Smith",
            email="bob.smith@testcorp.com",
            phone="+1-555-0102",
            address="202 Marketing Ave, Creative City",
            job_title="Content Marketing Lead",
            department_id=self.dept_marketing.id,
            user_id=self.employee_user2.id,
            salary=6500.00,
            hire_date=date(2025, 6, 1),
            status="active",
        )

        db.session.add_all([self.mgr_profile, self.emp1_profile, self.emp2_profile])
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
                    "test_admin_emp",
                    "test_mgr_emp",
                    "test_emp1",
                    "test_emp2",
                    "new_user_account",
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
    # 1. CRUD Operations (Admin)
    # -------------------------------------------------------------------------
    def test_admin_create_employee_success(self):
        """Admin can successfully create a new employee with all fields."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            "/employees/create",
            data={
                "employee_id": "EMP-9001",
                "first_name": "Catherine",
                "last_name": "Miller",
                "email": "c.miller@testcorp.com",
                "phone": "+1-555-0199",
                "address": "450 Enterprise Blvd, Suite 200",
                "job_title": "Product Analyst",
                "department_id": self.dept_engineering.id,
                "hire_date": "2026-02-01",
                "salary": 7200.00,
                "status": "active",
                "user_id": 0,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"EMP-9001", res.data)
        self.assertIn(b"Catherine Miller", res.data)

        # Verify in PostgreSQL
        emp = Employee.query.filter_by(employee_id="EMP-9001").first()
        self.assertIsNotNone(emp)
        self.assertEqual(emp.full_name, "Catherine Miller")
        self.assertEqual(emp.email, "c.miller@testcorp.com")
        self.assertEqual(emp.phone, "+1-555-0199")
        self.assertEqual(emp.job_title, "Product Analyst")
        self.assertEqual(emp.department_id, self.dept_engineering.id)
        self.assertEqual(float(emp.salary), 7200.00)
        self.assertEqual(emp.status, "active")

    def test_admin_view_employee_detail(self):
        """Admin can view the comprehensive employee detail page."""
        self.login_as(self.admin_user, "AdminPass12345!")

        # Add a task and attendance for emp1
        task = Task(title="Build API Auth", assigned_to_id=self.emp1_profile.id, status="pending")
        att = Attendance(employee_id=self.emp1_profile.id, date=date.today(), status="present")
        db.session.add_all([task, att])
        db.session.commit()

        res = self.client.get(f"/employees/{self.emp1_profile.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)
        self.assertIn(b"EMP-ENG01", res.data)
        self.assertIn(b"Senior Backend Engineer", res.data)
        self.assertIn(b"Build API Auth", res.data)
        self.assertIn(b"101 Dev Lane", res.data)

    def test_admin_edit_employee(self):
        """Admin can update an existing employee's information."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            f"/employees/{self.emp1_profile.id}/edit",
            data={
                "employee_id": "EMP-ENG01",  # Same ID should not fail uniqueness
                "first_name": "Alice",
                "last_name": "Johnson-Updated",
                "email": "alice.updated@testcorp.com",
                "phone": "+1-555-9999",
                "address": "999 New Address St",
                "job_title": "Principal Architect",
                "department_id": self.dept_engineering.id,
                "hire_date": "2024-03-15",
                "salary": 11000.00,
                "status": "on_leave",
                "user_id": self.employee_user1.id,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson-Updated", res.data)
        self.assertIn(b"Principal Architect", res.data)

        # Verify PostgreSQL updated
        emp = Employee.query.get(self.emp1_profile.id)
        self.assertEqual(emp.last_name, "Johnson-Updated")
        self.assertEqual(emp.email, "alice.updated@testcorp.com")
        self.assertEqual(emp.job_title, "Principal Architect")
        self.assertEqual(float(emp.salary), 11000.00)
        self.assertEqual(emp.status, "on_leave")

    def test_admin_delete_employee(self):
        """Admin can delete an employee, safely unassigning corporate tasks."""
        self.login_as(self.admin_user, "AdminPass12345!")

        # Create a task assigned to emp2
        task = Task(title="Write Marketing Blog", assigned_to_id=self.emp2_profile.id, status="in_progress")
        db.session.add(task)
        db.session.commit()
        task_id = task.id
        emp_id = self.emp2_profile.id

        res = self.client.post(f"/employees/{emp_id}/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"deleted successfully", res.data)

        # Verify employee removed from DB
        self.assertIsNone(Employee.query.get(emp_id))

        # Verify task is safely unassigned (not deleted)
        reloaded_task = Task.query.get(task_id)
        self.assertIsNotNone(reloaded_task)
        self.assertIsNone(reloaded_task.assigned_to_id)

    # -------------------------------------------------------------------------
    # 2. Form Validations
    # -------------------------------------------------------------------------
    def test_create_employee_required_fields(self):
        """Form rejects submission when required fields are missing."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            "/employees/create",
            data={
                "employee_id": "",
                "first_name": "",
                "last_name": "",
                "email": "",
                "job_title": "",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Employee ID is required.", res.data)
        self.assertIn(b"First name is required.", res.data)
        self.assertIn(b"Corporate email is required.", res.data)
        self.assertIn(b"Job title is required.", res.data)

    def test_create_employee_duplicate_employee_id(self):
        """Form rejects creation when employee_id already exists."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            "/employees/create",
            data={
                "employee_id": "EMP-ENG01",  # already belongs to Alice Johnson
                "first_name": "Duplicate",
                "last_name": "Test",
                "email": "unique.email@testcorp.com",
                "job_title": "Tester",
                "status": "active",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Employee ID &#39;EMP-ENG01&#39; is already assigned", res.data)

    def test_create_employee_duplicate_email(self):
        """Form rejects creation when corporate email already exists."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            "/employees/create",
            data={
                "employee_id": "EMP-NEW99",
                "first_name": "Duplicate",
                "last_name": "Email",
                "email": "alice.j@testcorp.com",  # already belongs to Alice
                "job_title": "Tester",
                "status": "active",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Email &#39;alice.j@testcorp.com&#39; is already in use", res.data)

    def test_create_employee_invalid_email_format(self):
        """Form rejects invalid email formatting."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.post(
            "/employees/create",
            data={
                "employee_id": "EMP-FORMAT",
                "first_name": "Format",
                "last_name": "Check",
                "email": "not-an-email",
                "job_title": "QA",
                "status": "active",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Please enter a valid email address.", res.data)

    # -------------------------------------------------------------------------
    # 3. Search & Filter
    # -------------------------------------------------------------------------
    def test_search_by_name(self):
        """Search query filters directory by employee first or last name."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.get("/employees?q=Alice")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)
        self.assertNotIn(b"Bob Smith", res.data)

    def test_search_by_employee_id(self):
        """Search query filters directory by exact or partial employee ID."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.get("/employees?q=MKT01")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Bob Smith", res.data)
        self.assertNotIn(b"Alice Johnson", res.data)

    def test_filter_by_department(self):
        """Department dropdown filters directory to that department only."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.get(f"/employees?department_id={self.dept_marketing.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Bob Smith", res.data)
        self.assertNotIn(b"Alice Johnson", res.data)

    def test_filter_by_job_title(self):
        """Job title filter matches substring in employee job title."""
        self.login_as(self.admin_user, "AdminPass12345!")

        res = self.client.get("/employees?job_title=Backend")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)
        self.assertNotIn(b"Bob Smith", res.data)

    # -------------------------------------------------------------------------
    # 4. Role-Based Permissions
    # -------------------------------------------------------------------------
    def test_anonymous_redirected_to_login(self):
        """Anonymous visitors are redirected to /auth/login."""
        endpoints = [
            "/employees",
            f"/employees/{self.emp1_profile.id}",
            "/employees/create",
            f"/employees/{self.emp1_profile.id}/edit",
        ]
        for url in endpoints:
            res = self.client.get(url, follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn("/auth/login", res.headers["Location"])

    def test_manager_scoped_to_assigned_department_only(self):
        """Manager only sees employees from their assigned department (Engineering)."""
        self.login_as(self.manager_user, "MgrPass12345!")

        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 200)
        # Engineering employees visible
        self.assertIn(b"Alice Johnson", res.data)
        self.assertIn(b"Marcus Vance", res.data)
        # Marketing employee NOT visible
        self.assertNotIn(b"Bob Smith", res.data)

    def test_manager_can_view_department_employee_profile(self):
        """Manager can view detailed profile of employee in their department."""
        self.login_as(self.manager_user, "MgrPass12345!")

        res = self.client.get(f"/employees/{self.emp1_profile.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)

    def test_manager_forbidden_from_other_department_profile(self):
        """Manager receives HTTP 403 when attempting to view employee from another department."""
        self.login_as(self.manager_user, "MgrPass12345!")

        # emp2 is Marketing, manager is Engineering
        res = self.client.get(f"/employees/{self.emp2_profile.id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_manager_forbidden_from_create_edit_delete(self):
        """Manager receives HTTP 403 on mutation routes."""
        self.login_as(self.manager_user, "MgrPass12345!")

        # Create
        res_create = self.client.get("/employees/create")
        self.assertEqual(res_create.status_code, 403)

        # Edit
        res_edit = self.client.get(f"/employees/{self.emp1_profile.id}/edit")
        self.assertEqual(res_edit.status_code, 403)

        # Delete
        res_delete = self.client.post(f"/employees/{self.emp1_profile.id}/delete")
        self.assertEqual(res_delete.status_code, 403)

    def test_employee_forbidden_from_directory_list(self):
        """Regular employee is forbidden from accessing the employee directory (HTTP 403)."""
        self.login_as(self.employee_user1, "EmpPass12345!")

        res = self.client.get("/employees")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_employee_can_view_own_profile(self):
        """Regular employee can view their own profile."""
        self.login_as(self.employee_user1, "EmpPass12345!")

        res = self.client.get(f"/employees/{self.emp1_profile.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)

    def test_employee_view_own_profile_via_shortcut(self):
        """Regular employee visiting /employees/profile redirects to their profile."""
        self.login_as(self.employee_user1, "EmpPass12345!")

        res = self.client.get("/employees/profile", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Alice Johnson", res.data)

    def test_employee_forbidden_from_other_employee_profile(self):
        """Regular employee receives HTTP 403 when trying to view someone else's profile."""
        self.login_as(self.employee_user1, "EmpPass12345!")

        # emp1 tries to view emp2
        res = self.client.get(f"/employees/{self.emp2_profile.id}")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

    def test_employee_forbidden_from_create_edit_delete(self):
        """Regular employee receives HTTP 403 on mutation routes."""
        self.login_as(self.employee_user1, "EmpPass12345!")

        # Create
        res_create = self.client.get("/employees/create")
        self.assertEqual(res_create.status_code, 403)

        # Edit
        res_edit = self.client.get(f"/employees/{self.emp1_profile.id}/edit")
        self.assertEqual(res_edit.status_code, 403)

        # Delete
        res_delete = self.client.post(f"/employees/{self.emp1_profile.id}/delete")
        self.assertEqual(res_delete.status_code, 403)


if __name__ == "__main__":
    unittest.main()

