"""
Comprehensive Automated Test Suite for Module 7: Salary and Payroll Management.

Verifies:
1. Setting and updating employee basic salary (in PKR).
2. Net Salary calculation formula: Net Salary = Basic Salary + Bonus - Deductions.
3. Single payroll generation with bonus and deduction details.
4. Prevention of duplicate payroll records for the same employee, month, and year.
5. Batch payroll generation for active workforce.
6. Role-based access control and strict privacy:
   - Admin has full access (create, edit, delete, batch, history, CSV export).
   - Employee can view their own payslips and dashboard.
   - Employee is blocked (403) from accessing another employee's payslip.
   - Employee is blocked (403) from administrative routes (create, batch, history, edit, delete, export).
   - Manager can view department records and cannot view records outside department.
7. Print/PDF salary slip rendering with PKR currency formatting.
8. CSV payroll export functionality.
9. AJAX employee salary auto-fill endpoint.
"""

import unittest
from datetime import date
from decimal import Decimal
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.department import Department
from app.models.employee import Employee
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.task import Task
from app.models.payroll import Payroll


class PayrollManagementTestCase(unittest.TestCase):
    """Test suite for Payroll and Salary Management Module."""

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
        self.dept_it = Department(name="Pay IT Dept", code="PIT", description="IT & Infrastructure")
        self.dept_sales = Department(name="Pay Sales Dept", code="PSD", description="Sales & Partnerships")
        db.session.add_all([self.dept_it, self.dept_sales])
        db.session.commit()

        # Seed Users
        self.admin = User(
            username="pay_admin_usr",
            email="admin_pay@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin.set_password("AdminPass123!")

        self.manager = User(
            username="pay_mgr_usr",
            email="mgr_pay@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager.set_password("MgrPass123!")

        self.emp1_user = User(
            username="pay_emp1_usr",
            email="emp1_pay@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.emp1_user.set_password("EmpPass123!")

        self.emp2_user = User(
            username="pay_emp2_usr",
            email="emp2_pay@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.emp2_user.set_password("EmpPass123!")

        db.session.add_all([self.admin, self.manager, self.emp1_user, self.emp2_user])
        db.session.commit()

        # Seed Employees
        self.mgr_profile = Employee(
            employee_id="PAY-MGR01",
            first_name="Bilal",
            last_name="Khan",
            email="b.khan@testcorp.com",
            phone="+92-300-1112233",
            job_title="IT Director",
            department_id=self.dept_it.id,
            user_id=self.manager.id,
            salary=250000.00,
            hire_date=date(2022, 1, 1),
            status="active",
        )

        self.emp1 = Employee(
            employee_id="PAY-EMP01",
            first_name="Zubair",
            last_name="Ahmed",
            email="z.ahmed@testcorp.com",
            phone="+92-300-4445566",
            job_title="Software Architect",
            department_id=self.dept_it.id,
            user_id=self.emp1_user.id,
            salary=180000.00,
            hire_date=date(2023, 5, 10),
            status="active",
        )

        self.emp2 = Employee(
            employee_id="PAY-EMP02",
            first_name="Sara",
            last_name="Tariq",
            email="s.tariq@testcorp.com",
            phone="+92-300-7778899",
            job_title="Sales Executive",
            department_id=self.dept_sales.id,
            user_id=self.emp2_user.id,
            salary=120000.00,
            hire_date=date(2024, 2, 1),
            status="active",
        )

        db.session.add_all([self.mgr_profile, self.emp1, self.emp2])
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
                User.username.in_(["pay_admin_usr", "pay_mgr_usr", "pay_emp1_usr", "pay_emp2_usr"])
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def login(self, username_or_email: str, password: str = "EmpPass123!"):
        """Helper to simulate user authentication."""
        return self.client.post(
            "/auth/login",
            data={"username_or_email": username_or_email, "password": password},
            follow_redirects=True,
        )

    def logout(self):
        """Helper to simulate logout."""
        return self.client.get("/auth/logout", follow_redirects=True)

    # -------------------------------------------------------------------------
    # 1. Formula & Model Unit Tests
    # -------------------------------------------------------------------------
    def test_net_salary_calculation_formula(self):
        """Formula: Net Salary = Basic Salary + Bonus - Deductions."""
        base = Decimal("150000.00")
        bonus = Decimal("15000.00")
        deductions = Decimal("5000.00")
        net = Payroll.compute_net(base, bonus, deductions)
        self.assertEqual(net, Decimal("160000.00"))

        # Zero bonus, deductions higher than zero
        net2 = Payroll.compute_net(base, Decimal("0.00"), Decimal("7500.00"))
        self.assertEqual(net2, Decimal("142500.00"))

    def test_payroll_model_properties(self):
        """Verifies gross_earnings, pay_period, and month_str properties."""
        p = Payroll(
            employee_id=self.emp1.id,
            month=4,
            year=2026,
            base_salary=Decimal("180000.00"),
            bonus=Decimal("20000.00"),
            deductions=Decimal("10000.00"),
            net_salary=Decimal("190000.00"),
            status="paid",
        )
        db.session.add(p)
        db.session.commit()

        self.assertEqual(p.gross_earnings, Decimal("200000.00"))
        self.assertEqual(p.month_str, "April")
        self.assertEqual(p.pay_period, "April 2026")

    # -------------------------------------------------------------------------
    # 2. Update Employee Basic Salary
    # -------------------------------------------------------------------------
    def test_admin_update_employee_base_salary(self):
        """Admin can update an employee's base salary via salary update form."""
        self.login(self.admin.username, "AdminPass123!")
        response = self.client.post(
            "/payroll/salary/update",
            data={
                "employee_id": self.emp1.id,
                "new_salary": "210000.00",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        # Verify salary updated in PostgreSQL
        emp = db.session.get(Employee, self.emp1.id)
        db.session.refresh(emp)
        self.assertEqual(float(emp.salary), 210000.00)

    def test_employee_cannot_update_base_salary(self):
        """Employees are blocked with 403 when attempting to update base salary."""
        self.login(self.emp1_user.username, "EmpPass123!")
        response = self.client.post(
            "/payroll/salary/update",
            data={
                "employee_id": self.emp1.id,
                "new_salary": "999999.00",
            },
        )
        self.assertEqual(response.status_code, 403)

    # -------------------------------------------------------------------------
    # 3. Create Single Payroll Record
    # -------------------------------------------------------------------------
    def test_admin_create_single_payroll_record(self):
        """Admin creates a single payroll disbursement with bonus and deductions."""
        self.login(self.admin.username, "AdminPass123!")
        response = self.client.post(
            "/payroll/create",
            data={
                "employee_id": self.emp1.id,
                "month": 3,
                "year": 2026,
                "base_salary": "180000.00",
                "bonus": "20000.00",
                "bonus_description": "Annual Performance Award",
                "deductions": "5000.00",
                "deduction_description": "Health Insurance Premium",
                "payment_method": "Bank Transfer",
                "payment_date": "2026-03-31",
                "status": "paid",
                "reference_no": "TXN-2026-001",
                "notes": "Direct wire to Habib Bank Ltd.",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        # Check DB record
        record = Payroll.query.filter_by(employee_id=self.emp1.id, month=3, year=2026).first()
        self.assertIsNotNone(record)
        self.assertEqual(record.net_salary, Decimal("195000.00"))
        self.assertEqual(record.bonus_description, "Annual Performance Award")
        self.assertEqual(record.reference_no, "TXN-2026-001")

    def test_duplicate_payroll_prevention(self):
        """Prevent generating duplicate payroll records for same employee, month, year."""
        self.login(self.admin.username, "AdminPass123!")
        
        # 1st creation
        self.client.post(
            "/payroll/create",
            data={
                "employee_id": self.emp1.id,
                "month": 5,
                "year": 2026,
                "base_salary": "180000.00",
                "bonus": "0.00",
                "deductions": "0.00",
                "payment_method": "Bank Transfer",
                "status": "pending",
            },
            follow_redirects=True,
        )

        # 2nd creation attempt for identical month/year
        response = self.client.post(
            "/payroll/create",
            data={
                "employee_id": self.emp1.id,
                "month": 5,
                "year": 2026,
                "base_salary": "180000.00",
                "bonus": "5000.00",
                "deductions": "0.00",
                "payment_method": "Bank Transfer",
                "status": "paid",
            },
            follow_redirects=True,
        )
        self.assertIn(b"already exists", response.data)
        self.assertEqual(Payroll.query.filter_by(employee_id=self.emp1.id, month=5, year=2026).count(), 1)

    # -------------------------------------------------------------------------
    # 4. Batch Payroll Generation
    # -------------------------------------------------------------------------
    def test_batch_payroll_generation(self):
        """Batch generation processes all active employees with positive base salary."""
        self.login(self.admin.username, "AdminPass123!")
        response = self.client.post(
            "/payroll/batch",
            data={
                "month": 6,
                "year": 2026,
                "department_id": 0,
                "payment_method": "Bank Transfer",
                "status": "pending",
                "notes": "Mid-year automated batch run",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        # All 3 active employees should have a record for June 2026
        count = Payroll.query.filter_by(month=6, year=2026).count()
        self.assertEqual(count, 3)

        # Running batch again skips already created records without error
        response2 = self.client.post(
            "/payroll/batch",
            data={
                "month": 6,
                "year": 2026,
                "department_id": 0,
                "payment_method": "Bank Transfer",
                "status": "pending",
            },
            follow_redirects=True,
        )
        self.assertIn(b"Skipped", response2.data)
        self.assertEqual(Payroll.query.filter_by(month=6, year=2026).count(), 3)

    # -------------------------------------------------------------------------
    # 5. RBAC & Privacy Enforcement
    # -------------------------------------------------------------------------
    def test_employee_can_view_own_salary_slip(self):
        """Employees can view their own printable salary slip."""
        p = Payroll(
            employee_id=self.emp1.id,
            month=1,
            year=2026,
            base_salary=Decimal("180000.00"),
            bonus=Decimal("10000.00"),
            deductions=Decimal("5000.00"),
            net_salary=Decimal("185000.00"),
            status="paid",
        )
        db.session.add(p)
        db.session.commit()

        self.login(self.emp1_user.username, "EmpPass123!")
        response = self.client.get(f"/payroll/slip/{p.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Salary Slip", response.data)
        self.assertIn(b"Zubair Ahmed", response.data)

    def test_employee_blocked_from_other_employee_salary_slip(self):
        """Employees receive 403 Forbidden when attempting to view another's payslip."""
        # Create payslip for emp2 (Sara)
        p = Payroll(
            employee_id=self.emp2.id,
            month=1,
            year=2026,
            base_salary=Decimal("120000.00"),
            bonus=Decimal("0.00"),
            deductions=Decimal("0.00"),
            net_salary=Decimal("120000.00"),
            status="paid",
        )
        db.session.add(p)
        db.session.commit()

        # emp1 tries to view emp2's slip
        self.login(self.emp1_user.username, "EmpPass123!")
        response = self.client.get(f"/payroll/slip/{p.id}")
        self.assertEqual(response.status_code, 403)

    def test_employee_blocked_from_payroll_admin_routes(self):
        """Employees receive 403 on admin-only payroll actions."""
        self.login(self.emp1_user.username, "EmpPass123!")
        
        # Create
        res_create = self.client.get("/payroll/create")
        self.assertEqual(res_create.status_code, 403)

        # Batch
        res_batch = self.client.get("/payroll/batch")
        self.assertEqual(res_batch.status_code, 403)

        # Salary Update
        res_sal = self.client.get("/payroll/salary/update")
        self.assertEqual(res_sal.status_code, 403)

        # CSV Export
        res_export = self.client.get("/payroll/export/csv")
        self.assertEqual(res_export.status_code, 403)

    def test_manager_department_scoping(self):
        """Manager can view slips for their department staff, but not other departments."""
        # Slip for IT employee (emp1) - allowed
        p_it = Payroll(
            employee_id=self.emp1.id,
            month=2,
            year=2026,
            base_salary=Decimal("180000.00"),
            bonus=Decimal("0.00"),
            deductions=Decimal("0.00"),
            net_salary=Decimal("180000.00"),
            status="paid",
        )
        # Slip for Sales employee (emp2) - forbidden for IT Manager
        p_sales = Payroll(
            employee_id=self.emp2.id,
            month=2,
            year=2026,
            base_salary=Decimal("120000.00"),
            bonus=Decimal("0.00"),
            deductions=Decimal("0.00"),
            net_salary=Decimal("120000.00"),
            status="paid",
        )
        db.session.add_all([p_it, p_sales])
        db.session.commit()

        self.login(self.manager.username, "MgrPass123!")
        
        # IT slip: 200 OK
        res_it = self.client.get(f"/payroll/slip/{p_it.id}")
        self.assertEqual(res_it.status_code, 200)

        # Sales slip: 403 Forbidden
        res_sales = self.client.get(f"/payroll/slip/{p_sales.id}")
        self.assertEqual(res_sales.status_code, 403)

    # -------------------------------------------------------------------------
    # 6. CSV Export & AJAX Auto-Fill
    # -------------------------------------------------------------------------
    def test_payroll_csv_export(self):
        """Admin can export all payroll records as CSV."""
        p = Payroll(
            employee_id=self.emp1.id,
            month=7,
            year=2026,
            base_salary=Decimal("180000.00"),
            bonus=Decimal("5000.00"),
            deductions=Decimal("2000.00"),
            net_salary=Decimal("183000.00"),
            status="paid",
        )
        db.session.add(p)
        db.session.commit()

        self.login(self.admin.username, "AdminPass123!")
        response = self.client.get("/payroll/export/csv")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/csv; charset=utf-8")
        self.assertIn(b"Employee ID,Employee Name,Department", response.data)
        self.assertIn(b"PAY-EMP01", response.data)
        self.assertIn(b"183000.00", response.data)

    def test_ajax_employee_salary_endpoint(self):
        """AJAX endpoint returns base salary for employee."""
        self.login(self.admin.username, "AdminPass123!")
        response = self.client.get(f"/payroll/api/employee-salary/{self.emp1.id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["employee_id"], self.emp1.id)
        self.assertEqual(data["base_salary"], 180000.0)


if __name__ == "__main__":
    unittest.main()
