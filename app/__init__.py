"""
Application Factory Module for Company Management System.

Initializes Flask, binds extensions, registers Blueprints, and sets up error handlers.
"""

import os
from flask import Flask, render_template
from app.config import config_by_name
from app.extensions import db, login_manager, migrate, csrf


def create_app(config_name: str | None = None) -> Flask:
    """
    Application factory pattern for Flask.
    
    :param config_name: Configuration key ('development', 'production', 'testing').
    :return: Configured Flask application instance.
    """
    if config_name is None:
        if os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production":
            config_name = "production"
        else:
            config_name = os.getenv("FLASK_ENV", "development").lower()

    flask_app = Flask(__name__)
    config_class = config_by_name.get(config_name, config_by_name["default"])
    flask_app.config.from_object(config_class)

    # In production, validate critical settings and enforce strict debug=False
    if config_name == "production":
        flask_app.config["DEBUG"] = False
        flask_app.config["TESTING"] = False
        if hasattr(config_class, "validate"):
            config_class.validate()

    # Dynamic reload of environment database URI & secret key if provided
    from app.config import get_db_configuration
    db_uri, is_configured = get_db_configuration()
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
    flask_app.config["POSTGRES_IS_CONFIGURED"] = is_configured
    if os.getenv("SECRET_KEY"):
        flask_app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

    # Initialize Flask Extensions
    db.init_app(flask_app)
    migrate.init_app(flask_app, db)
    csrf.init_app(flask_app)
    login_manager.init_app(flask_app)

    # Import models so SQLAlchemy is aware of them
    with flask_app.app_context():
        import app.models  # noqa: F401

    # Register Blueprints
    from app.blueprints.main import main_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.api import api_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.employee import employee_bp
    from app.blueprints.department import department_bp
    from app.blueprints.attendance import attendance_bp
    from app.blueprints.payroll import payroll_bp
    from app.blueprints.task import task_bp
    from app.blueprints.report import report_bp

    flask_app.register_blueprint(main_bp)
    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(api_bp)
    flask_app.register_blueprint(admin_bp)
    flask_app.register_blueprint(employee_bp)
    flask_app.register_blueprint(department_bp)
    flask_app.register_blueprint(attendance_bp)
    flask_app.register_blueprint(payroll_bp, url_prefix="/payroll")
    flask_app.register_blueprint(task_bp, url_prefix="/tasks")
    flask_app.register_blueprint(report_bp, url_prefix="/reports")

    # Register Error Handlers
    register_error_handlers(flask_app)

    # Register CLI Commands
    register_cli_commands(flask_app)

    # Context Processors and Template Filters
    @flask_app.context_processor
    def inject_global_template_vars():
        return {
            "app_name": "Nexus Enterprise CMS",
            "current_year": 2026,
            "currency_symbol": "PKR",
            "timezone_name": "Asia/Karachi",
            "environment": flask_app.config.get("ENV", "development"),
        }

    @flask_app.template_filter("currency_pkr")
    def currency_pkr_filter(value):
        try:
            val = float(value) if value is not None else 0.0
            return f"PKR {val:,.2f}"
        except (ValueError, TypeError):
            return "PKR 0.00"

    @flask_app.template_filter("karachi_time")
    def karachi_time_filter(dt, fmt="%b %d, %Y %I:%M %p"):
        if not dt:
            return ""
        if hasattr(dt, "strftime"):
            from datetime import timezone
            from zoneinfo import ZoneInfo
            if getattr(dt, "tzinfo", None) is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo("Asia/Karachi")).strftime(fmt)
        return str(dt)

    return flask_app


def register_error_handlers(app: Flask):
    """Registers standard HTTP error handlers."""
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template("errors/403.html", error=error), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html", error=error), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template("errors/500.html", error=error), 500


def register_cli_commands(app: Flask):
    """Registers CLI management commands."""
    import click
    from sqlalchemy import text

    @app.cli.command("init-db")
    def init_db_command():
        """Creates PostgreSQL database tables defined in models."""
        is_configured = app.config.get("POSTGRES_IS_CONFIGURED", False)
        if not is_configured:
            click.echo(
                click.style("Error: PostgreSQL database is not configured. Please configure .env with PostgreSQL credentials.", fg="red")
            )
            return

        try:
            with app.app_context():
                db.create_all()
            click.echo(click.style("Success: PostgreSQL database tables created successfully!", fg="green"))
        except Exception as exc:
            click.echo(click.style(f"Database Initialization Failed: {exc}", fg="red"))

    @app.cli.command("test-db")
    def test_db_command():
        """Tests the PostgreSQL connection from CLI."""
        from app.blueprints.main.routes import check_postgres_connection
        click.echo("Testing PostgreSQL connection...")
        diag = check_postgres_connection()
        if diag["connected"]:
            click.echo(click.style(f"Connected successfully!", fg="green"))
            click.echo(f"Database: {diag['database_name']}")
            click.echo(f"Latency:  {diag['latency_ms']} ms")
            click.echo(f"Tables:   {diag['tables']}")
            click.echo(f"Version:  {diag['version']}")
        else:
            click.echo(click.style(f"Connection Failed: {diag['message']}", fg="red"))
            if diag.get("error"):
                click.echo(f"Error details: {diag['error']}")
            if diag.get("instructions"):
                click.echo("\nRemediation Steps:")
                for step in diag["instructions"]:
                    click.echo(f"  {step}")

    @app.cli.command("create-admin")
    @click.option("--username", help="Administrator username", default=None)
    @click.option("--email", help="Administrator email address", default=None)
    @click.option(
        "--password",
        help="Administrator password (min 8 characters).",
        default=None,
    )
    def create_admin_command(username, email, password):
        """Securely provisions an initial Administrator account via interactive prompts or CLI flags."""
        from app.models.user import User
        from app.extensions import db

        if not username:
            username = click.prompt("Admin Username", default="admin")
        if not email:
            email = click.prompt("Admin Email", default="admin@company.com")
        if not password:
            click.echo("\n[Security Note: Typed password characters are invisible on screen. Type your password and press Enter]")
            password = click.prompt(
                "Admin Password (min 8 chars)",
                hide_input=True,
                confirmation_prompt=True,
            )

        if len(password) < 8:
            click.echo(click.style("Error: Password must be at least 8 characters long.", fg="red"))
            return

        username = username.strip()
        email = email.strip().lower()

        try:
            with app.app_context():
                existing_user = User.query.filter(
                    (User.username == username) | (User.email == email)
                ).first()
                if existing_user:
                    click.echo(
                        click.style(
                            f"Error: A user with username '{username}' or email '{email}' already exists.",
                            fg="red",
                        )
                    )
                    return

                admin = User(username=username, email=email, role="admin", is_active=True)
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
                click.echo(
                    click.style(
                        f"\nSuccess: Administrator '{username}' ({email}) created successfully!",
                        fg="green",
                    )
                )
        except Exception as exc:
            click.echo(click.style(f"Admin Creation Failed: {exc}", fg="red"))

    @app.cli.command("init-admin-env")
    def init_admin_env_command():
        """Provisions an initial Admin using environment variables (ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD)."""
        import os
        from app.models.user import User
        from app.extensions import db

        username = os.getenv("ADMIN_USERNAME", "").strip()
        email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "").strip()

        if not username or not email or not password:
            click.echo(
                click.style(
                    "Error: ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD must all be defined in environment.",
                    fg="red",
                )
            )
            return

        if len(password) < 8:
            click.echo(click.style("Error: ADMIN_PASSWORD must be at least 8 characters long.", fg="red"))
            return

        try:
            with app.app_context():
                existing = User.query.filter(
                    (User.username == username) | (User.email == email)
                ).first()
                if existing:
                    click.echo(
                        click.style(
                            f"Notice: User with username '{username}' or email '{email}' already exists.",
                            fg="yellow",
                        )
                    )
                    return

                admin = User(username=username, email=email, role="admin", is_active=True)
                admin.set_password(password)
                db.session.add(admin)
                db.session.commit()
                click.echo(
                    click.style(
                        f"Success: Administrator '{username}' provisioned from environment variables!",
                        fg="green",
                    )
                )
        except Exception as exc:
            click.echo(click.style(f"Environment Admin Provisioning Failed: {exc}", fg="red"))
