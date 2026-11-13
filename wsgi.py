"""
WSGI Application Entry Point for Production Deployment (Render, Gunicorn, PaaS).

Exposes the WSGI callable `app` for production servers.
Usage:
    gunicorn wsgi:app
    gunicorn -c gunicorn_config.py wsgi:app
"""

import os
from dotenv import load_dotenv

# Load local environment variables if .env file exists
load_dotenv()

from app import create_app

# WSGI entry point is exclusively for production WSGI servers (Gunicorn)
target_env = os.getenv("WSGI_ENV", "production")

# Instantiate Flask application for production
app = create_app(target_env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
