"""
Idempotent PostgreSQL migration for Payroll model enhancements.
Adds:
- bonus_description (VARCHAR 255)
- deduction_description (VARCHAR 255)
- payment_method (VARCHAR 50 DEFAULT 'Bank Transfer')
- reference_no (VARCHAR 100)
- notes (TEXT)
"""

import sys
from sqlalchemy import text
from app import create_app
from app.extensions import db


def migrate():
    app = create_app("development")
    with app.app_context():
        print(f"Connecting to PostgreSQL: {app.config['SQLALCHEMY_DATABASE_URI']}")

        sqls = [
            """
            ALTER TABLE payrolls 
            ADD COLUMN IF NOT EXISTS bonus_description VARCHAR(255);
            """,
            """
            ALTER TABLE payrolls 
            ADD COLUMN IF NOT EXISTS deduction_description VARCHAR(255);
            """,
            """
            ALTER TABLE payrolls 
            ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'Bank Transfer';
            """,
            """
            ALTER TABLE payrolls 
            ADD COLUMN IF NOT EXISTS reference_no VARCHAR(100);
            """,
            """
            ALTER TABLE payrolls 
            ADD COLUMN IF NOT EXISTS notes TEXT;
            """,
        ]

        with db.engine.connect() as conn:
            for sql in sqls:
                conn.execute(text(sql))
            conn.commit()

        print("Payroll enhancement migration completed successfully.")


if __name__ == "__main__":
    migrate()

