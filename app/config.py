"""
Application Configuration Module.

Supports multiple environments: Development, Production, and Testing.
Strictly configured for PostgreSQL using Flask-SQLAlchemy.
"""

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Strictly PostgreSQL fallback placeholder when no environment variables are defined yet.
# This allows Flask to initialize without crashing while keeping the dialect strictly PostgreSQL.
UNCONFIGURED_POSTGRES_PLACEHOLDER = (
    "postgresql+psycopg://unconfigured_user:unconfigured_password@127.0.0.1:5432/unconfigured_company_db"
)


def get_db_configuration() -> tuple[str, bool]:
    """
    Constructs a PostgreSQL database URI from environment variables.
    
    Priority:
    1. DATABASE_URL (Standard connection string, common on Render/Supabase/Neon)
    2. Discrete variables: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    
    Returns:
        tuple[str, bool]: (database_uri, is_configured)
    """
    database_url = os.getenv("DATABASE_URL", "").strip()

    # Gracefully handle common user typo: DATABASE_URL=DATABASE_URL=... or surrounding quotes
    while database_url.startswith("DATABASE_URL="):
        database_url = database_url[len("DATABASE_URL="):].strip()
    database_url = database_url.strip("\"'")

    if database_url:
        # Normalize legacy 'postgres://' schema often returned by cloud providers
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
            # Explicitly use modern psycopg 3 driver for PostgreSQL
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return database_url, True

    # Check discrete variables
    db_name = os.getenv("DB_NAME", "").strip()
    if db_name:
        db_user = os.getenv("DB_USER", "postgres").strip()
        db_password = os.getenv("DB_PASSWORD", "").strip()
        db_host = os.getenv("DB_HOST", "localhost").strip()
        db_port = os.getenv("DB_PORT", "5432").strip()
        db_sslmode = os.getenv("DB_SSLMODE", "").strip()

        # URL encode password to handle special characters safely
        encoded_password = quote_plus(db_password) if db_password else ""
        auth = f"{db_user}:{encoded_password}@" if db_user else ""
        
        uri = f"postgresql+psycopg://{auth}{db_host}:{db_port}/{db_name}"
        if db_sslmode:
            uri += f"?sslmode={db_sslmode}"
        return uri, True

    # Unconfigured state - strictly PostgreSQL placeholder
    return UNCONFIGURED_POSTGRES_PLACEHOLDER, False


class Config:
    """Base configuration class."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-secret-key-change-in-env")
    
    # Strictly PostgreSQL
    _db_uri, _is_configured = get_db_configuration()
    SQLALCHEMY_DATABASE_URI = _db_uri
    POSTGRES_IS_CONFIGURED = _is_configured
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # PostgreSQL connection pool settings for high reliability
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "connect_timeout": 15,
        },
    }


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    ENV = "development"


class ProductionConfig(Config):
    """Production configuration (Render / Production Cloud)."""
    DEBUG = False
    TESTING = False
    ENV = "production"

    @classmethod
    def validate(cls):
        """Validates that critical production secrets and DB connection are set."""
        secret_key = os.getenv("SECRET_KEY", "").strip()
        if not secret_key or secret_key == "dev-insecure-secret-key-change-in-env":
            raise ValueError(
                "CRITICAL: A secure, non-default SECRET_KEY environment variable is required in production! "
                "Generate one using: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        db_uri, is_configured = get_db_configuration()
        if not is_configured or "unconfigured" in db_uri:
            raise ValueError(
                "CRITICAL: PostgreSQL DATABASE_URL must be configured in production! "
                "Render PostgreSQL connection format: postgresql+psycopg://user:password@host:5432/dbname"
            )


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
