"""
Database migration script to ensure leave_requests table and attendance indexes exist in PostgreSQL.
"""

from sqlalchemy import text, inspect
from app import create_app
from app.extensions import db


def migrate():
    app = create_app()
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f"Existing tables in PostgreSQL: {existing_tables}")

        with engine.connect() as conn:
            if "leave_requests" not in existing_tables:
                print("Creating leave_requests table...")
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS leave_requests (
                        id SERIAL PRIMARY KEY,
                        employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
                        leave_type VARCHAR(50) NOT NULL,
                        start_date DATE NOT NULL,
                        end_date DATE NOT NULL,
                        reason TEXT,
                        status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                        reviewed_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        reviewed_at TIMESTAMP,
                        review_notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                    );
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leave_requests_employee_id ON leave_requests(employee_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leave_requests_start_date ON leave_requests(start_date);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leave_requests_end_date ON leave_requests(end_date);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_leave_requests_status ON leave_requests(status);"))
                conn.commit()
                print("leave_requests table created successfully!")
            else:
                print("leave_requests table already exists.")

            # Ensure unique constraint on attendance (employee_id, date)
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_employee_attendance_date ON attendance(employee_id, date);
            """))
            conn.commit()
            print("Attendance unique index verified!")


if __name__ == "__main__":
    migrate()

