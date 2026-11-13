"""
Flask Extensions Initialization Module.

Instantiates extensions without binding them to any specific app instance,
enabling the application factory pattern.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

# Flask-SQLAlchemy instance
db = SQLAlchemy()

# Flask-Migrate instance
migrate = Migrate()

# Flask-WTF CSRF instance
csrf = CSRFProtect()

# Flask-Login instance
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "info"

