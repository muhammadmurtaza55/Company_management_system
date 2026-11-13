"""
Database migration script to add employee_id, email, phone, and address to employees table.
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
                WHERE table_name = 'employees'
            """))
            existing_cols = {row[0] for row in cols_res.fetchall()}
            print(f"Existing columns: {existing_cols}")

            # Add employee_id
            if "employee_id" not in existing_cols:
                print("Adding employee_id column...")
                conn.execute(text("ALTER TABLE employees ADD COLUMN employee_id VARCHAR(32);"))
                conn.commit()

            # Add email
            if "email" not in existing_cols:
                print("Adding email column...")
                conn.execute(text("ALTER TABLE employees ADD COLUMN email VARCHAR(120);"))
                conn.commit()

            # Add phone
            if "phone" not in existing_cols:
                print("Adding phone column...")
                conn.execute(text("ALTER TABLE employees ADD COLUMN phone VARCHAR(32);"))
                conn.commit()

            # Add address
            if "address" not in existing_cols:
                print("Adding address column...")
                conn.execute(text("ALTER TABLE employees ADD COLUMN address TEXT;"))
                conn.commit()

            # Backfill any NULL employee_id and email
            conn.execute(text("""
                UPDATE employees 
                SET employee_id = 'EMP-' || LPAD(id::text, 4, '0') 
                WHERE employee_id IS NULL;
            """))
            conn.execute(text("""
                UPDATE employees 
                SET email = 'employee' || id::text || '@company.local' 
                WHERE email IS NULL;
            """))
            conn.commit()

            # Add unique indexes / constraints if not present
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_employee_id ON employees(employee_id);
            """))
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_employees_email ON employees(email);
            """))
            conn.commit()

            # Set NOT NULL
            conn.execute(text("ALTER TABLE employees ALTER COLUMN employee_id SET NOT NULL;"))
            conn.execute(text("ALTER TABLE employees ALTER COLUMN email SET NOT NULL;"))
            conn.commit()

            print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()

