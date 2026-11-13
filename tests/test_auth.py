"""
Comprehensive Automated Test Suite for Company Management System Authentication.

Verifies:
1. Secure password hashing (passwords never stored as plain text).
2. Login with valid/invalid credentials, email/username, and deactivated state.
3. Session management and logout.
4. Role-based access control (Admin, Manager, Employee permissions).
5. Protection of Admin-only routes from Manager and Employee access.
6. Admin user provisioning and status toggling.
7. Profile password updates.
"""

import unittest
from app import create_app
from app.extensions import db
from app.models.user import User


class AuthenticationTestCase(unittest.TestCase):
    """Test suite for authentication, Flask-Login sessions, and RBAC."""

    @classmethod
    def setUpClass(cls):
        """Initializes application and ensures database tables exist."""
        cls.app = create_app("testing")
        cls.app.config["TESTING"] = True
        cls.app.config["WTF_CSRF_ENABLED"] = False  # Facilitates testing forms
        cls.client = cls.app.test_client()

        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        """Prepares isolated test accounts before each test."""
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Clean up any residual test accounts
        self.cleanup_test_users()

        # Create 3 users for the three system roles
        self.admin = User(
            username="test_admin",
            email="admin@testcorp.com",
            role="admin",
            is_active=True,
        )
        self.admin.set_password("AdminSecurePassword123!")

        self.manager = User(
            username="test_manager",
            email="manager@testcorp.com",
            role="manager",
            is_active=True,
        )
        self.manager.set_password("ManagerSecurePassword123!")

        self.employee = User(
            username="test_employee",
            email="employee@testcorp.com",
            role="employee",
            is_active=True,
        )
        self.employee.set_password("EmployeeSecurePassword123!")

        # Create a deactivated user for testing
        self.inactive_user = User(
            username="test_inactive",
            email="inactive@testcorp.com",
            role="employee",
            is_active=False,
        )
        self.inactive_user.set_password("InactivePassword123!")

        db.session.add_all([self.admin, self.manager, self.employee, self.inactive_user])
        db.session.commit()

    def tearDown(self):
        """Cleans up created test records after each test."""
        self.cleanup_test_users()
        self.app_context.pop()

    def cleanup_test_users(self):
        """Removes all test users created by this suite."""
        try:
            User.query.filter(
                User.username.in_([
                    "test_admin",
                    "test_manager",
                    "test_employee",
                    "test_inactive",
                    "newly_created_user",
                    "cli_test_admin",
                ])
            ).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # -------------------------------------------------------------------------
    # 1. Password Hashing Security Tests
    # -------------------------------------------------------------------------
    def test_passwords_never_stored_in_plain_text(self):
        """Verifies that plain-text passwords are never stored in the database."""
        raw_password = "AdminSecurePassword123!"
        self.assertNotEqual(self.admin.password_hash, raw_password)
        self.assertFalse(raw_password in self.admin.password_hash)
        # Verify hash uses strong scrypt or pbkdf2 algorithm
        self.assertTrue(
            self.admin.password_hash.startswith("scrypt:") or self.admin.password_hash.startswith("pbkdf2:")
        )

    def test_password_verification(self):
        """Verifies check_password correctly validates and invalidates passwords."""
        self.assertTrue(self.admin.check_password("AdminSecurePassword123!"))
        self.assertFalse(self.admin.check_password("WrongPassword123!"))
        self.assertFalse(self.admin.check_password(""))

    def test_role_properties(self):
        """Verifies role-checking properties and helpers."""
        self.assertTrue(self.admin.is_admin)
        self.assertFalse(self.admin.is_manager)
        self.assertFalse(self.admin.is_employee)
        self.assertTrue(self.admin.has_role("admin", "manager"))

        self.assertFalse(self.manager.is_admin)
        self.assertTrue(self.manager.is_manager)
        self.assertFalse(self.manager.is_employee)
        self.assertTrue(self.manager.has_role("manager"))

        self.assertFalse(self.employee.is_admin)
        self.assertFalse(self.employee.is_manager)
        self.assertTrue(self.employee.is_employee)
        self.assertFalse(self.employee.has_role("admin", "manager"))

    # -------------------------------------------------------------------------
    # 2. Login & Logout Tests
    # -------------------------------------------------------------------------
    def test_login_with_valid_username(self):
        """Tests successful login using username."""
        res = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "test_admin",
                "password": "AdminSecurePassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, test_admin!", res.data)
        self.assertIn(b"Sign Out", res.data)

    def test_login_with_valid_email(self):
        """Tests successful login using email address."""
        res = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "admin@testcorp.com",
                "password": "AdminSecurePassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome back, test_admin!", res.data)

    def test_login_with_invalid_password(self):
        """Tests that login fails with incorrect password and shows clear error."""
        res = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "test_admin",
                "password": "WrongPassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Invalid credentials", res.data)
        self.assertNotIn(b"Sign Out", res.data)

    def test_login_with_nonexistent_user(self):
        """Tests that login fails for non-existent users."""
        res = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "ghost_user",
                "password": "AnyPassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Invalid credentials", res.data)

    def test_login_with_deactivated_account(self):
        """Tests that deactivated accounts cannot log in."""
        res = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "test_inactive",
                "password": "InactivePassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your account has been deactivated", res.data)

    def test_logout(self):
        """Tests logging out terminates the session."""
        # Log in first
        self.client.post(
            "/auth/login",
            data={
                "username_or_email": "test_employee",
                "password": "EmployeeSecurePassword123!",
            },
        )
        # Log out
        res = self.client.get("/auth/logout", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"You have been signed out successfully.", res.data)
        self.assertIn(b"Sign In", res.data)

    # -------------------------------------------------------------------------
    # 3. Role-Based Access Control (RBAC) & Page Protection Tests
    # -------------------------------------------------------------------------
    def test_anonymous_access_to_admin_pages_blocked(self):
        """Anonymous users attempting to access /auth/users are redirected to login."""
        res = self.client.get("/auth/users", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/auth/login", res.headers["Location"])

    def test_employee_access_to_admin_pages_forbidden(self):
        """Employees are strictly blocked from accessing Admin-only pages (HTTP 403)."""
        # Login as Employee
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_employee", "password": "EmployeeSecurePassword123!"},
        )
        # Attempt to access Admin User Directory
        res = self.client.get("/auth/users")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

        # Attempt to access User Creation Page
        res_create = self.client.get("/auth/users/create")
        self.assertEqual(res_create.status_code, 403)

    def test_manager_access_to_admin_pages_forbidden(self):
        """Managers are strictly blocked from accessing Admin-only pages (HTTP 403)."""
        # Login as Manager
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_manager", "password": "ManagerSecurePassword123!"},
        )
        # Attempt to access Admin User Directory
        res = self.client.get("/auth/users")
        self.assertEqual(res.status_code, 403)
        self.assertIn(b"403 Forbidden", res.data)

        # Attempt to access User Creation Page
        res_create = self.client.get("/auth/users/create")
        self.assertEqual(res_create.status_code, 403)

    def test_admin_access_to_admin_pages_permitted(self):
        """Admins can successfully access Admin-only pages (HTTP 200)."""
        # Login as Admin
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        # Access Admin User Directory
        res = self.client.get("/auth/users")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"User Account Administration", res.data)
        self.assertIn(b"test_admin", res.data)
        self.assertIn(b"test_manager", res.data)
        self.assertIn(b"test_employee", res.data)

        # Access User Creation Page
        res_create = self.client.get("/auth/users/create")
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b"Provision New User Account", res_create.data)

    # -------------------------------------------------------------------------
    # 4. User Provisioning by Admin Only Tests
    # -------------------------------------------------------------------------
    def test_admin_can_create_new_user(self):
        """Verifies that an Admin can successfully provision a new account with a role."""
        # Login as Admin
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        # Submit new user creation form
        res = self.client.post(
            "/auth/users/create",
            data={
                "username": "newly_created_user",
                "email": "newuser@testcorp.com",
                "role": "employee",
                "password": "NewUserPassword123!",
                "confirm_password": "NewUserPassword123!",
                "is_active": True,
                "first_name": "New",
                "last_name": "Employee",
                "job_title": "Frontend Engineer",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"created successfully with role &#39;Employee&#39;", res.data)

        # Verify user exists in PostgreSQL with hashed password
        created_user = User.query.filter_by(username="newly_created_user").first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.email, "newuser@testcorp.com")
        self.assertEqual(created_user.role, "employee")
        self.assertTrue(created_user.check_password("NewUserPassword123!"))
        self.assertNotEqual(created_user.password_hash, "NewUserPassword123!")

        # Verify newly created user can log in
        # Logout admin
        self.client.get("/auth/logout")
        # Login as new user
        res_login = self.client.post(
            "/auth/login",
            data={
                "username_or_email": "newly_created_user",
                "password": "NewUserPassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Welcome back, newly_created_user!", res_login.data)

    def test_non_admin_cannot_post_to_create_user(self):
        """Verifies that employees cannot POST to create user endpoint."""
        # Login as Employee
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_employee", "password": "EmployeeSecurePassword123!"},
        )
        res = self.client.post(
            "/auth/users/create",
            data={
                "username": "unauthorized_user",
                "email": "unauth@testcorp.com",
                "role": "admin",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        self.assertEqual(res.status_code, 403)
        # Ensure user was not created in DB
        unauth = User.query.filter_by(username="unauthorized_user").first()
        self.assertIsNone(unauth)

    def test_admin_can_toggle_user_status(self):
        """Verifies Admin can deactivate and activate user accounts."""
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        # Deactivate employee
        res = self.client.post(
            f"/auth/users/{self.employee.id}/toggle-status",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        emp = db.session.get(User, self.employee.id)
        self.assertFalse(emp.is_active)
        self.assertIn(b"deactivated successfully", res.data)

        # Reactivate employee
        res2 = self.client.post(
            f"/auth/users/{self.employee.id}/toggle-status",
            follow_redirects=True,
        )
        self.assertEqual(res2.status_code, 200)
        emp2 = db.session.get(User, self.employee.id)
        self.assertTrue(emp2.is_active)
        self.assertIn(b"activated successfully", res2.data)

    def test_toggle_status_rejects_get_requests(self):
        """Verifies GET requests to toggle-status are rejected with HTTP 405 Method Not Allowed."""
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        res = self.client.get(f"/auth/users/{self.employee.id}/toggle-status")
        self.assertEqual(res.status_code, 405)

    def test_non_admin_cannot_toggle_user_status(self):
        """Manager and Employee are forbidden from toggling user status (HTTP 403)."""
        # Test as manager
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_manager", "password": "ManagerSecurePassword123!"},
        )
        res_mgr = self.client.post(f"/auth/users/{self.employee.id}/toggle-status")
        self.assertEqual(res_mgr.status_code, 403)
        self.client.get("/auth/logout")

        # Test as employee
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_employee", "password": "EmployeeSecurePassword123!"},
        )
        res_emp = self.client.post(f"/auth/users/{self.employee.id}/toggle-status")
        self.assertEqual(res_emp.status_code, 403)

    def test_admin_cannot_deactivate_self(self):
        """Verifies an Admin cannot deactivate their own account."""
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        res = self.client.post(
            f"/auth/users/{self.admin.id}/toggle-status",
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        adm = db.session.get(User, self.admin.id)
        self.assertTrue(adm.is_active)
        self.assertIn(b"cannot deactivate your own administrative account", res.data)

    def test_users_page_renders_csrf_token_in_toggle_form(self):
        """Verifies the /auth/users page includes proper POST form and CSRF token for toggle-status."""
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_admin", "password": "AdminSecurePassword123!"},
        )
        res = self.client.get("/auth/users")
        self.assertEqual(res.status_code, 200)
        self.assertIn(f'action="/auth/users/{self.employee.id}/toggle-status"'.encode(), res.data)
        self.assertIn(b'name="csrf_token"', res.data)

    def test_csrf_protection_on_toggle_status(self):
        """Verifies CSRF protection blocks requests without valid token and allows valid token."""
        try:
            self.app.config["WTF_CSRF_ENABLED"] = True
            with self.client:
                # Login as admin with CSRF token
                login_page = self.client.get("/auth/login")
                import re
                token_match = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', login_page.data.decode("utf-8"))
                self.assertIsNotNone(token_match, "Login form must render CSRF token when CSRF is enabled")
                token = token_match.group(1)

                login_res = self.client.post(
                    "/auth/login",
                    data={
                        "username_or_email": "test_admin",
                        "password": "AdminSecurePassword123!",
                        "csrf_token": token,
                    },
                    follow_redirects=True,
                )
                self.assertEqual(login_res.status_code, 200)

                # Attempt toggle POST without CSRF token -> Expect 400 Bad Request
                res_no_csrf = self.client.post(f"/auth/users/{self.employee.id}/toggle-status")
                self.assertEqual(res_no_csrf.status_code, 400)

                # Fetch users page to get new CSRF token
                users_page = self.client.get("/auth/users")
                self.assertEqual(users_page.status_code, 200)
                token_match2 = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', users_page.data.decode("utf-8"))
                self.assertIsNotNone(token_match2, "Toggle form in users page must render CSRF token")
                user_token = token_match2.group(1)

                # Submit toggle POST with valid CSRF token -> Expect 200 (redirect to users page)
                res_valid_csrf = self.client.post(
                    f"/auth/users/{self.employee.id}/toggle-status",
                    data={"csrf_token": user_token},
                    follow_redirects=True,
                )
                self.assertEqual(res_valid_csrf.status_code, 200)
                emp = db.session.get(User, self.employee.id)
                self.assertFalse(emp.is_active)
                self.assertIn(b"deactivated successfully", res_valid_csrf.data)

                # Reactivate with valid CSRF token
                users_page2 = self.client.get("/auth/users")
                token_match3 = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', users_page2.data.decode("utf-8"))
                self.assertIsNotNone(token_match3)
                reactivate_token = token_match3.group(1)

                res_reactivate = self.client.post(
                    f"/auth/users/{self.employee.id}/toggle-status",
                    data={"csrf_token": reactivate_token},
                    follow_redirects=True,
                )
                self.assertEqual(res_reactivate.status_code, 200)
                emp_reactivated = db.session.get(User, self.employee.id)
                self.assertTrue(emp_reactivated.is_active)
                self.assertIn(b"activated successfully", res_reactivate.data)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    # -------------------------------------------------------------------------
    # 5. Profile Password Modification Tests
    # -------------------------------------------------------------------------
    def test_change_password_on_profile(self):
        """Tests that users can update their password via profile page."""
        self.client.post(
            "/auth/login",
            data={"username_or_email": "test_employee", "password": "EmployeeSecurePassword123!"},
        )
        res = self.client.post(
            "/auth/profile",
            data={
                "current_password": "EmployeeSecurePassword123!",
                "new_password": "BrandNewPassword123!",
                "confirm_password": "BrandNewPassword123!",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Your password has been updated successfully!", res.data)

        # Verify old password no longer works and new password works
        emp = User.query.filter_by(username="test_employee").first()
        self.assertFalse(emp.check_password("EmployeeSecurePassword123!"))
        self.assertTrue(emp.check_password("BrandNewPassword123!"))


if __name__ == "__main__":
    unittest.main()

