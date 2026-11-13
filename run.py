"""
Application Entry Point.

Starts the Flask development server or exposes the application instance for WSGI servers (Gunicorn).
"""

import sys
import os

# Auto-inject virtual environment site-packages if running with standard python outside venv
base_dir = os.path.dirname(os.path.abspath(__file__))
venv_site_packages = os.path.join(base_dir, "venv", "Lib", "site-packages")
if os.path.exists(venv_site_packages) and venv_site_packages not in sys.path:
    sys.path.insert(0, venv_site_packages)

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from app import create_app

# Instantiate application
is_production = bool(os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production")
default_env = "production" if is_production else "development"
env = os.getenv("FLASK_ENV", default_env)
app = create_app(env)

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0" if is_production else "127.0.0.1")
    port = int(os.getenv("PORT", 5000))
    # Never enable debug mode in production
    if is_production or env == "production":
        debug = False
    else:
        debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    print(f"\n=======================================================")
    print(f" * Company Management System (Nexus CMS)")
    print(f" * Environment: {app.config.get('ENV', 'development')}")
    print(f" * URL: http://{host}:{port}")
    print(f" * PostgreSQL Status Check: http://{host}:{port}/db-test")
    print(f"=======================================================\n")

    app.run(host=host, port=port, debug=debug)

