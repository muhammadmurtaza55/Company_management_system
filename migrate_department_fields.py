"""
Database migration script to add manager_id and updated_at to departments table.
"""

from sqlalchemy import text
from app import create_app
from app.extensions import db


def migrate():
    app = create_app()
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            # Check existing columns
            cols_res = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'departments'
            """))
            existing_cols = {row[0] for row in cols_res.fetchall()}
            print(f"Existing departments columns: {existing_cols}")

            # Add manager_id
            if "manager_id" not in existing_cols:
                print("Adding manager_id column to departments...")
                conn.execute(text("""
                    ALTER TABLE departments 
                    ADD COLUMN manager_id INTEGER REFERENCES employees(id) ON DELETE SET NULL;
                """))
                conn.commit()

            # Add updated_at
            if "updated_at" not in existing_cols:
                print("Adding updated_at column to departments...")
                conn.execute(text("""
                    ALTER TABLE departments 
                    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                """))
                conn.commit()

            # Create index on manager_id
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_departments_manager_id ON departments(manager_id);
            """))
            conn.commit()

            print("Department migration completed successfully!")


if __name__ == "__main__":
    migrate()

