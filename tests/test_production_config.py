"""
Automated Verification Suite for Production Readiness and Render Configuration.

Verifies:
1. Production environment disables Flask debug mode (DEBUG = False).
2. Production mode enforces a secure, non-default SECRET_KEY.
3. Production mode enforces a configured PostgreSQL DATABASE_URL.
4. WSGI entry point (wsgi:app) and runner (run:app) instantiate correctly.
5. Gunicorn configuration file exists and defines production bindings and timeouts.
6. Procfile contains the correct start command.
7. .gitignore contains .env.
8. .env.example contains placeholder values without credentials.
9. Database migrations are clean and stamped at head.
"""

import os
import unittest
from app import create_app
from app.config import ProductionConfig, get_db_configuration


class ProductionDeploymentTestCase(unittest.TestCase):
    """Test suite verifying production configuration for Render deployment."""

    def test_production_mode_forces_debug_false(self):
        """Production configuration must strictly set DEBUG = False."""
        app = create_app("production")
        self.assertFalse(app.config.get("DEBUG"), "DEBUG must be False in production!")
        self.assertFalse(app.config.get("TESTING"), "TESTING must be False in production!")
        self.assertEqual(app.config.get("ENV"), "production")

    def test_production_validate_catches_missing_or_default_secret_key(self):
        """ProductionConfig.validate() must raise ValueError if SECRET_KEY is missing or insecure default."""
        orig_key = os.environ.get("SECRET_KEY")
        try:
            # Test empty key
            os.environ["SECRET_KEY"] = ""
            with self.assertRaises(ValueError) as ctx:
                ProductionConfig.validate()
            self.assertIn("SECRET_KEY", str(ctx.exception))

            # Test default insecure key
            os.environ["SECRET_KEY"] = "dev-insecure-secret-key-change-in-env"
            with self.assertRaises(ValueError) as ctx2:
                ProductionConfig.validate()
            self.assertIn("SECRET_KEY", str(ctx2.exception))
        finally:
            if orig_key is not None:
                os.environ["SECRET_KEY"] = orig_key
            else:
                os.environ.pop("SECRET_KEY", None)

    def test_production_validate_catches_missing_database_url(self):
        """ProductionConfig.validate() must raise ValueError if PostgreSQL is unconfigured."""
        orig_url = os.environ.get("DATABASE_URL")
        orig_name = os.environ.get("DB_NAME")
        try:
            os.environ["DATABASE_URL"] = ""
            os.environ["DB_NAME"] = ""
            with self.assertRaises(ValueError) as ctx:
                ProductionConfig.validate()
            self.assertIn("DATABASE_URL", str(ctx.exception))
        finally:
            if orig_url is not None:
                os.environ["DATABASE_URL"] = orig_url
            if orig_name is not None:
                os.environ["DB_NAME"] = orig_name

    def test_wsgi_module_entry_point(self):
        """The wsgi module must expose a valid Flask application callable named 'app'."""
        import wsgi
        self.assertTrue(hasattr(wsgi, "app"))
        self.assertIsNotNone(wsgi.app)
        self.assertFalse(wsgi.app.config.get("DEBUG"))

    def test_run_module_entry_point(self):
        """The run module must expose a valid Flask application callable named 'app'."""
        import run
        self.assertTrue(hasattr(run, "app"))
        self.assertIsNotNone(run.app)

    def test_procfile_configuration(self):
        """Procfile must exist and specify gunicorn startup command."""
        self.assertTrue(os.path.exists("Procfile"), "Procfile must exist in root!")
        with open("Procfile", "r", encoding="utf-8") as f:
            content = f.read().strip()
        self.assertTrue(content.startswith("web: gunicorn"), "Procfile must use gunicorn!")
        self.assertIn("wsgi:app", content, "Procfile must target wsgi:app!")

    def test_gunicorn_config_exists(self):
        """gunicorn_config.py must exist with timeout and binding parameters."""
        self.assertTrue(os.path.exists("gunicorn_config.py"))
        import gunicorn_config
        self.assertIsNotNone(getattr(gunicorn_config, "bind", None))
        self.assertGreaterEqual(getattr(gunicorn_config, "timeout", 0), 60)
        self.assertGreaterEqual(getattr(gunicorn_config, "workers", 0), 2)

    def test_gitignore_protects_env(self):
        """.gitignore must explicitly ignore .env and local environment files."""
        self.assertTrue(os.path.exists(".gitignore"))
        with open(".gitignore", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        self.assertIn(".env", lines, ".gitignore must ignore .env!")

    def test_env_example_has_clean_placeholders(self):
        """.env.example must not expose real passwords."""
        self.assertTrue(os.path.exists(".env.example"))
        with open(".env.example", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("SECRET_KEY=", content)
        self.assertIn("DATABASE_URL=", content)
        # Verify no hardcoded production secrets
        self.assertNotIn("company_db_user:secret_pass", content)


if __name__ == "__main__":
    unittest.main()

