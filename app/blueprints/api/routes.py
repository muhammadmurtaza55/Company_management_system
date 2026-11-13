"""
REST API Endpoints for System Diagnostics and Health Checks.
"""

import sys
from datetime import datetime, timezone
from flask import jsonify, current_app
from app.blueprints.api import api_bp
from app.blueprints.main.routes import check_postgres_connection
from app.extensions import db


@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint for container / load balancer monitoring."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version,
        "environment": current_app.config.get("ENV", "unknown"),
    })


@api_bp.route("/db-status", methods=["GET"])
def db_status():
    """JSON API to test and inspect PostgreSQL database connection status."""
    diagnostics = check_postgres_connection()
    status_code = 200 if diagnostics["connected"] else (503 if diagnostics["configured"] else 400)
    return jsonify(diagnostics), status_code


@api_bp.route("/init-db", methods=["POST"])
def init_db():
    """
    Initializes PostgreSQL database tables from models.
    Safe to call; creates tables if they do not already exist.
    """
    diagnostics = check_postgres_connection()
    if not diagnostics["connected"]:
        return jsonify({
            "success": False,
            "message": "Cannot create tables: PostgreSQL database is not reachable.",
            "diagnostics": diagnostics,
        }), 400

    try:
        db.create_all()
        # Query tables after creation
        updated_diag = check_postgres_connection()
        return jsonify({
            "success": True,
            "message": "Successfully initialized database tables in PostgreSQL!",
            "tables": updated_diag["tables"],
        }), 200
    except Exception as exc:
        return jsonify({
            "success": False,
            "message": "Failed to create database tables.",
            "error": str(exc),
        }), 500

