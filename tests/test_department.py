"""
Department Management Module Test Suite.

Automated tests for department CRUD operations, manager assignments,
staff allocation, workforce metrics, accidental deletion prevention,
and role-based permissions against PostgreSQL.
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


class DepartmentModuleTestCase(unittest.TestCase):
    """Integration test suite for the Department Management Module."""

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
            username="dept_admin_test",
            email="dept_admin@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin.set_password("AdminPass12345!")

        # 2. Manager User
        self.manager = User(
            username="dept_mgr_test",
            email="dept_mgr@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager.set_password("MgrPass12345!")

        # 3. Employee User
        self.employee_user = User(
            username="dept_emp_test",
            email="dept_emp@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.employee_user.set_password("EmpPass12345!")

        db.session.add_all([self.admin, self.manager, self.employee_user])
        db.session.commit()

        # Seed Department
        self.dept_it = Department(
            name="Information Technology",
            code="IT",
            description="Core systems infrastructure and security",
        )
        db.session.add(self.dept_it)
        db.session.commit()

        # Seed Manager Employee
        self.emp_mgr = Employee(
            employee_id="EMP-IT01",
            first_name="David",
            last_name="Clark",
            email="d.clark@testcorp.com",
            phone="+1-555-8801",
            job_title="Director of IT",
            department_id=self.dept_it.id,
            user_id=self.manager.id,
            salary=12500.00,
            hire_date=date(2022, 5, 1),
            status="active",
        )

        # Seed Regular Employee 1
        self.emp_staff = Employee(
            employee_id="EMP-IT02",
            first_name="Elena",
            last_name="Rostova",
            email="e.rostova@testcorp.com",
            phone="+1-555-8802",
            job_title="DevOps Specialist",
            department_id=self.dept_it.id,
            user_id=self.employee_user.id,
            salary=8500.00,
            hire_date=date(2024, 1, 15),
            status="active",
        )

        # Seed Unassigned Employee
        self.emp_unassigned = Employee(
            employee_id="EMP-UN01",
            first_name="Fiona",
            last_name="Gallagher",
            email="f.gallagher@testcorp.com",
            phone="+1-555-8803",
            job_title="Junior Analyst",
            department_id=None,
            salary=5000.00,
            hire_date=date(2025, 2, 1),
            status="active",
        )

        db.session.add_all([self.emp_mgr, self.emp_staff, self.emp_unassigned])
        db.session.commit()

        # Set manager on department
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
                User.username.in_(["dept_admin_test", "dept_mgr_test", "dept_emp_test"])
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
    # 1. Department CRUD Operations
    # -------------------------------------------------------------------------
    def test_create_department_success(self):
        """Admin can successfully create a new department with code and manager."""
        self.login_as(self.admin, "AdminPass12345!")

        res = self.client.post(
            "/departments/create",
            data={
                "name": "Research & Development",
                "code": "RND",
                "description": "Product innovation and engineering R&D",
                "manager_id": self.emp_unassigned.id,
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Research &amp; Development", res.data)
        self.assertIn(b"RND", res.data)

        # Verify in PostgreSQL
        dept = Department.query.filter_by(code="RND").first()
        self.assertIsNotNone(dept)
        self.assertEqual(dept.name, "Research & Development")
        self.assertEqual(dept.manager_id, self.emp_unassigned.id)
        # Verify manager's department_id was also synchronized
        emp = Employee.query.get(self.emp_unassigned.id)
        self.assertEqual(emp.department_id, dept.id)

    def test_view_all_departments(self):
        """Admin and Manager can view the department directory."""
        self.login_as(self.admin, "AdminPass12345!")

        res = self.client.get("/departments")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Information Technology", res.data)
        self.assertIn(b"IT", res.data)
        self.assertIn(b"David Clark", res.data)

    def test_view_department_details(self):
        """Viewing a department displays KPI metrics, manager, and employee roster."""
        self.login_as(self.admin, "AdminPass12345!")

        res = self.client.get(f"/departments/{self.dept_it.id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Information Technology", res.data)
        self.assertIn(b"David Clark", res.data)  # Manager
        self.assertIn(b"Elena Rostova", res.data)  # Staff member
        self.assertIn(b"Director of IT", res.data)
        self.assertIn(b"DevOps Specialist", res.data)

    def test_edit_department(self):
        """Admin can update department name, description, and manager."""
        self.login_as(self.admin, "AdminPass12345!")

        res = self.client.post(
            f"/departments/{self.dept_it.id}/edit",
            data={
                "name": "Cloud Infrastructure & IT",
                "code": "IT",  # Same code should not fail uniqueness
                "description": "Updated infrastructure scope",
                "manager_id": self.emp_staff.id,  # Promote Elena to Manager
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cloud Infrastructure &amp; IT", res.data)

        # Verify PostgreSQL updated
        dept = Department.query.get(self.dept_it.id)
        self.assertEqual(dept.name, "Cloud Infrastructure & IT")
        self.assertEqual(dept.manager_id, self.emp_staff.id)

    # -------------------------------------------------------------------------
    # 2. Accidental Deletion Prevention
    # -------------------------------------------------------------------------
    def test_delete_department_blocked_when_employees_exist(self):
        """CRITICAL: Deleting a department with assigned employees is blocked to protect data."""
        self.login_as(self.admin, "AdminPass12345!")

        # dept_it has 2 employees (David Clark, Elena Rostova)
        self.assertGreater(len(self.dept_it.employees), 0)

        res = self.client.post(f"/departments/{self.dept_it.id}/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot delete department", res.data)
        self.assertIn(b"employee(s) are currently assigned", res.data)

        # Verify department STILL exists in PostgreSQL
        reloaded_dept = Department.query.get(self.dept_it.id)
        self.assertIsNotNone(reloaded_dept)

    def test_delete_empty_department_success(self):
        """An empty department without employees can be safely deleted."""
        self.login_as(self.admin, "AdminPass12345!")

        # Create an empty department
        empty_dept = Department(name="Temporary Unit", code="TMP", description="No staff")
        db.session.add(empty_dept)
        db.session.commit()
        empty_id = empty_dept.id

        res = self.client.post(f"/departments/{empty_id}/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"deleted successfully", res.data)

        # Verify department was removed from PostgreSQL
        self.assertIsNone(Department.query.get(empty_id))

    # -------------------------------------------------------------------------
    # 3. Employee Allocation & Removal
    # -------------------------------------------------------------------------
    def test_assign_employee_to_department(self):
        """Admin can assign an unassigned employee to a department."""
        self.login_as(self.admin, "AdminPass12345!")

        self.assertIsNone(self.emp_unassigned.department_id)

        res = self.client.post(
            f"/departments/{self.dept_it.id}/assign-employee",
            data={"employee_id": self.emp_unassigned.id},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"assigned to Information Technology successfully", res.data)

        # Verify in PostgreSQL
        emp = Employee.query.get(self.emp_unassigned.id)
        self.assertEqual(emp.department_id, self.dept_it.id)

    def test_remove_employee_from_department(self):
        """Admin can remove an employee from a department."""
        self.login_as(self.admin, "AdminPass12345!")

        res = self.client.post(
            f"/departments/{self.dept_it.id}/remove-employee/{self.emp_staff.id}",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"was removed from Information Technology", res.data)

        # Verify in PostgreSQL
        emp = Employee.query.get(self.emp_staff.id)
        self.assertIsNone(emp.department_id)

    def test_removing_manager_clears_department_manager_id(self):
        """Removing the department's manager also safely unsets manager_id on the department."""
        self.login_as(self.admin, "AdminPass12345!")

        self.assertEqual(self.dept_it.manager_id, self.emp_mgr.id)

        res = self.client.post(
            f"/departments/{self.dept_it.id}/remove-employee/{self.emp_mgr.id}",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        # Verify in PostgreSQL
        dept = Department.query.get(self.dept_it.id)
        self.assertIsNone(dept.manager_id)

    # -------------------------------------------------------------------------
    # 4. Department Statistics Calculations
    # -------------------------------------------------------------------------
    def test_department_statistics_properties(self):
        """Verifies computed properties for employee statistics and salary expenses."""
        dept = Department.query.get(self.dept_it.id)

        # David: 12500, Elena: 8500 (both active)
        self.assertEqual(dept.total_employees, 2)
        self.assertEqual(dept.active_employees_count, 2)
        self.assertEqual(dept.on_leave_count, 0)
        self.assertEqual(dept.total_salary_expense, 21000.00)
        self.assertEqual(dept.average_salary, 10500.00)

    # -------------------------------------------------------------------------
    # 5. Role-Based Permissions
    # -------------------------------------------------------------------------
    def test_anonymous_redirected_to_login(self):
        """Anonymous requests redirect to /auth/login."""
        res = self.client.get("/departments", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers["Location"])

    def test_manager_can_view_but_cannot_mutate(self):
        """Manager can view departments but cannot create, edit, or delete."""
        self.login_as(self.manager, "MgrPass12345!")

        # View list: OK
        res_list = self.client.get("/departments")
        self.assertEqual(res_list.status_code, 200)

        # View own department detail: OK
        res_detail = self.client.get(f"/departments/{self.dept_it.id}")
        self.assertEqual(res_detail.status_code, 200)

        # Create: Forbidden
        res_create = self.client.get("/departments/create")
        self.assertEqual(res_create.status_code, 403)

        # Edit: Forbidden
        res_edit = self.client.get(f"/departments/{self.dept_it.id}/edit")
        self.assertEqual(res_edit.status_code, 403)

        # Delete: Forbidden
        res_del = self.client.post(f"/departments/{self.dept_it.id}/delete")
        self.assertEqual(res_del.status_code, 403)

    def test_regular_employee_forbidden_from_admin_actions(self):
        """Regular employee is denied access to mutation routes."""
        self.login_as(self.employee_user, "EmpPass12345!")

        res_create = self.client.get("/departments/create")
        self.assertEqual(res_create.status_code, 403)

        res_edit = self.client.get(f"/departments/{self.dept_it.id}/edit")
        self.assertEqual(res_edit.status_code, 403)

        res_del = self.client.post(f"/departments/{self.dept_it.id}/delete")
        self.assertEqual(res_del.status_code, 403)


if __name__ == "__main__":
    unittest.main()

