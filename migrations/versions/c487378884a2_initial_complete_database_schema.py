
"""Initial complete database schema

Revision ID: c487378884a2
Revises:
Create Date: 2026-11-13 01:22:32
"""

from alembic import op
import sqlalchemy as sa

revision = 'c487378884a2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():

    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('email', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # 2. Departments table (manager FK added later)
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('manager_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_departments_code', 'departments', ['code'], unique=True)
    op.create_index('ix_departments_manager_id', 'departments', ['manager_id'])
    op.create_index('ix_departments_name', 'departments', ['name'], unique=True)

    # 3. Employees table
    op.create_table(
        'employees',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.String(32), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('department_id', sa.Integer(), nullable=True),
        sa.Column('first_name', sa.String(64), nullable=False),
        sa.Column('last_name', sa.String(64), nullable=False),
        sa.Column('email', sa.String(120), nullable=False),
        sa.Column('phone', sa.String(32), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('job_title', sa.String(100), nullable=False),
        sa.Column('hire_date', sa.Date(), nullable=True),
        sa.Column('salary', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['department_id'], ['departments.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index('ix_employees_email', 'employees', ['email'], unique=True)
    op.create_index('ix_employees_employee_id', 'employees', ['employee_id'], unique=True)

    # 4. Add circular manager foreign key after both tables exist
    op.create_foreign_key(
        'fk_departments_manager_id_employees',
        'departments',
        'employees',
        ['manager_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 5. Attendance table
    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('check_in', sa.Time(), nullable=True),
        sa.Column('check_out', sa.Time(), nullable=True),
        sa.Column('notes', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['employee_id'], ['employees.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'employee_id', 'date', name='uq_employee_attendance_date'
        )
    )
    op.create_index('ix_attendance_date', 'attendance', ['date'])
    op.create_index('ix_attendance_employee_id', 'attendance', ['employee_id'])
    op.create_index('ix_attendance_status', 'attendance', ['status'])

    # 6. Leave requests table
    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('leave_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['employee_id'], ['employees.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['reviewed_by_id'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_leave_requests_employee_id', 'leave_requests', ['employee_id'])
    op.create_index('ix_leave_requests_end_date', 'leave_requests', ['end_date'])
    op.create_index('ix_leave_requests_start_date', 'leave_requests', ['start_date'])
    op.create_index('ix_leave_requests_status', 'leave_requests', ['status'])

    # 7. Payrolls table
    op.create_table(
        'payrolls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('base_salary', sa.Numeric(12, 2), nullable=False),
        sa.Column('bonus', sa.Numeric(12, 2), nullable=False),
        sa.Column('bonus_description', sa.String(255), nullable=True),
        sa.Column('deductions', sa.Numeric(12, 2), nullable=False),
        sa.Column('deduction_description', sa.String(255), nullable=True),
        sa.Column('net_salary', sa.Numeric(12, 2), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('reference_no', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['employee_id'], ['employees.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'employee_id', 'month', 'year',
            name='uq_employee_payroll_month_year'
        )
    )
    op.create_index('ix_payrolls_employee_id', 'payrolls', ['employee_id'])

    # 8. Tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assigned_to_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['assigned_to_id'], ['employees.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['created_by_id'], ['users.id'], ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tasks_assigned_to_id', 'tasks', ['assigned_to_id'])


def downgrade():

    op.drop_index('ix_tasks_assigned_to_id', table_name='tasks')
    op.drop_table('tasks')

    op.drop_index('ix_payrolls_employee_id', table_name='payrolls')
    op.drop_table('payrolls')

    op.drop_index('ix_leave_requests_status', table_name='leave_requests')
    op.drop_index('ix_leave_requests_start_date', table_name='leave_requests')
    op.drop_index('ix_leave_requests_end_date', table_name='leave_requests')
    op.drop_index('ix_leave_requests_employee_id', table_name='leave_requests')
    op.drop_table('leave_requests')

    op.drop_index('ix_attendance_status', table_name='attendance')
    op.drop_index('ix_attendance_employee_id', table_name='attendance')
    op.drop_index('ix_attendance_date', table_name='attendance')
    op.drop_table('attendance')

    op.drop_constraint(
        'fk_departments_manager_id_employees',
        'departments',
        type_='foreignkey'
    )

    op.drop_index('ix_employees_employee_id', table_name='employees')
    op.drop_index('ix_employees_email', table_name='employees')
    op.drop_table('employees')

    op.drop_index('ix_departments_name', table_name='departments')
    op.drop_index('ix_departments_manager_id', table_name='departments')
    op.drop_index('ix_departments_code', table_name='departments')
    op.drop_table('departments')

    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
