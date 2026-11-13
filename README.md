# Nexus Enterprise - Company Management System (CMS)

A scalable, professional web application designed for comprehensive enterprise personnel, departmental hierarchy, and company operations management.

Built with **Python 3.14**, **Flask**, **Flask-SQLAlchemy**, **Flask-Login**, **PostgreSQL**, and **Bootstrap 5**. Configured for production deployment on **Render**.

---

## 🌟 Technology Stack

| Layer | Technology | Specification / Version |
| :--- | :--- | :--- |
| **Language** | Python | 3.14+ |
| **Web Framework** | Flask | 3.1.3 (Application Factory & Blueprints) |
| **Database** | PostgreSQL | Strictly PostgreSQL (via modern `psycopg 3` / `psycopg2`) |
| **ORM** | Flask-SQLAlchemy | 3.1.1 (SQLAlchemy 2.x) |
| **Authentication** | Flask-Login | 0.6.3 + Werkzeug password hashing |
| **Frontend** | HTML5, CSS3, JS | Bootstrap 5.3 + Bootstrap Icons |
| **Version Control** | Git & GitHub | Strict `.gitignore` policy |
| **Deployment** | Render | Gunicorn WSGI server & `Procfile` |

> ⚠️ **Database Policy Notice**: SQLite and MySQL are strictly prohibited in this codebase. Only PostgreSQL is supported to guarantee strict relational integrity, concurrent transactional locking, and cloud production readiness.

---

## 📂 Project Architecture

```
Company_managment_system/
│
├── .env.example              # Environment variables template (DO NOT commit real .env)
├── .gitignore                # Git ignore rules protecting secrets and cache
├── gunicorn_config.py        # Production Gunicorn worker, timeout, and log configuration
├── Procfile                  # Process manager file for Render (web: gunicorn ...)
├── render.yaml               # Infrastructure-as-Code Blueprint for one-click Render deployment
├── README.md                 # Complete documentation & setup instructions
├── requirements.txt          # Python production dependencies (Flask, Gunicorn, PostgreSQL drivers)
├── run.py                    # Local development runner & CLI administration
├── wsgi.py                   # Production WSGI entry point for Render & Gunicorn
│
├── migrations/               # Alembic database schema migrations
│   └── versions/             # Versioned schema revisions (auto-applied via flask db upgrade)
│
└── app/
    ├── __init__.py           # Application Factory (`create_app`), error handlers, CLI commands
    ├── config.py             # Multi-environment config (Development, Production, Testing)
    ├── extensions.py         # Flask extension instances (SQLAlchemy, Migrate, CSRF, LoginManager)
    │
    ├── blueprints/
    │   ├── admin/            # Executive Admin Dashboard & operational hubs
    │   ├── api/              # RESTful health checks & PostgreSQL connection diagnostics
    │   ├── attendance/       # Employee check-in/out, punctuality tracking & leave approvals
    │   ├── auth/             # Authentication, RBAC sessions, CSRF & user management
    │   ├── department/       # Department CRUD, manager assignment & deletion guards
    │   ├── employee/         # Employee profiles, directory search & filtering
    │   ├── main/             # Public landing page, role redirects & diagnostics
    │   ├── payroll/          # Salary configuration, batch generation & printable payslips
    │   ├── report/           # Executive reporting center with CSV exports & printable views
    │   └── task/             # Workflow task tracking, kanban board & deadline monitoring
    │
    ├── models/
    │   ├── __init__.py       # Model export registry and Flask-Login user loader
    │   ├── attendance.py     # Punch-clock logs, punctuality metrics & status tracking
    │   ├── department.py     # Company departments & structural hierarchy
    │   ├── employee.py       # Comprehensive personnel profiles with salary & contact info
    │   ├── leave_request.py  # Leave applications, date ranges & approval states
    │   ├── payroll.py        # Compensation disbursements, bonuses & deduction ledgers
    │   ├── task.py           # Work orders, priorities, assignments & overdue tracking
    │   └── user.py           # User authentication, PBKDF2 hashing & RBAC roles
    │
    ├── static/
    │   ├── css/style.css     # Custom enterprise design system extending Bootstrap 5
    │   └── js/main.js        # Dynamic AJAX diagnostics, currency formatting & DOM reactivity
    │
    └── templates/            # Fully responsive Bootstrap 5 templates
```

---

## 🚀 Local Quickstart Guide

### 1. Prerequisites
- **Python 3.14** (or Python 3.11+)
- **PostgreSQL** (installed locally, running in Docker, or hosted free on Render, Neon, or Supabase)

---

### 2. Clone and Setup Environment

In your terminal or PowerShell:

```bash
# Navigate to the project root
cd Company_managment_system

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
.\venv\Scripts\activate.bat
# Linux/macOS:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

---

### 3. Configure Environment Variables

1. Copy `.env.example` to create your private `.env` file:
   ```powershell
   copy .env.example .env
   ```
   *(On Linux/macOS use `cp .env.example .env`)*

2. Open `.env` and configure your settings:
   ```ini
   FLASK_APP=run.py
   FLASK_ENV=development
   FLASK_DEBUG=1
   SECRET_KEY=generate_a_random_32_character_secret_key_here

   # Option A: Full PostgreSQL URI (Recommended)
   DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/company_management_db

   # Option B: Discrete credentials (alternative if DATABASE_URL is not set)
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=company_management_db
   ```

> 🔒 **Security Notice**: `.env` is listed in `.gitignore` and must **never** be checked into version control.

---

### 4. Create the PostgreSQL Database

If using local PostgreSQL:
```bash
# Using PostgreSQL command line:
createdb company_management_db

# Or inside the PostgreSQL psql shell:
CREATE DATABASE company_management_db;
```

If using cloud PostgreSQL (e.g., Render, Neon, Supabase):
- Simply copy your PostgreSQL connection string into `DATABASE_URL` in `.env`.

---

### 5. Verify Database Connection and Initialize Tables

You can test the PostgreSQL connection directly from the command line:

```bash
# Test the PostgreSQL connection
flask --app run.py test-db

# Create initial database tables (users, departments, employees)
flask --app run.py init-db
```

---

### 6. Create Initial Administrator Account

Before logging in to the Admin Dashboard, provision your initial administrator account using the secure interactive CLI command (passwords are securely hashed and never hardcoded):

```bash
flask --app run.py create-admin
```
*(You will be prompted for username, email, and password with hidden input and strength validation).*

---

### 7. Run the Application

Start the Flask development server:

```bash
python run.py
```

The application will launch at:
- **Public Portal**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
- **Sign In Page**: [http://127.0.0.1:5000/auth/login](http://127.0.0.1:5000/auth/login)
- **Admin Dashboard**: [http://127.0.0.1:5000/admin/dashboard](http://127.0.0.1:5000/admin/dashboard) *(Requires Admin role)*
- **User Management (RBAC)**: [http://127.0.0.1:5000/auth/users](http://127.0.0.1:5000/auth/users) *(Admin only)*
- **Department Hub & Management**: [http://127.0.0.1:5000/departments](http://127.0.0.1:5000/departments) *(Admin & Manager)*
- **Add Department**: [http://127.0.0.1:5000/departments/create](http://127.0.0.1:5000/departments/create) *(Admin only)*
- **Employee Directory & Management**: [http://127.0.0.1:5000/employees](http://127.0.0.1:5000/employees) *(Admin & Manager scoped)*
- **Add Employee**: [http://127.0.0.1:5000/employees/create](http://127.0.0.1:5000/employees/create) *(Admin only)*
- **My Employee Profile**: [http://127.0.0.1:5000/employees/profile](http://127.0.0.1:5000/employees/profile) *(All logged-in staff)*
- **User Management (RBAC)**: [http://127.0.0.1:5000/auth/users](http://127.0.0.1:5000/auth/users) *(Admin only)*
- **Admin Module Quick Views**:
  - Departments: [http://127.0.0.1:5000/admin/departments](http://127.0.0.1:5000/admin/departments)
  - Attendance Ledger: [http://127.0.0.1:5000/admin/attendance](http://127.0.0.1:5000/admin/attendance)
  - Tasks & Workflow: [http://127.0.0.1:5000/admin/tasks](http://127.0.0.1:5000/admin/tasks)
  - Payroll Disbursements: [http://127.0.0.1:5000/admin/payroll](http://127.0.0.1:5000/admin/payroll)
- **PostgreSQL Diagnostic Test**: [http://127.0.0.1:5000/db-test](http://127.0.0.1:5000/db-test)
- **API Health Check**: [http://127.0.0.1:5000/api/health](http://127.0.0.1:5000/api/health)

---

### 8. Department Management Module Architecture & Safety Rules

The Department Management Module (`/departments`) integrates directly into the Admin Dashboard and handles organizational hierarchy:

#### Core Capabilities:
1. **Department CRUD**: Create, view, edit, and delete company operational units with unique codes (e.g. `ENG`, `FIN`, `HR`).
2. **Manager Assignment**: Assign qualified staff members as Department Managers / Heads of Department via dynamic dropdown selection.
3. **Staff Allocation & Roster**: Assign employees to departments, reassign or transfer between departments, and remove employees.
4. **Accidental Deletion Protection**: Strict server-side and modal validation preventing the deletion of any department that still has employees assigned (`assigned_count > 0`), protecting relational data integrity.
5. **Workforce Metrics & Financial KPIs**: Real-time aggregation of total employees, active count, on leave count, terminated count, total monthly salary expense, and average employee salary per department.

---

### 9. Employee Management Module Architecture & Permissions

The Employee Management Module (`/employees`) is built on Flask Blueprints and strictly tied to PostgreSQL:

#### Role-Based Permission Matrix:
| Action | Admin | Manager | Employee |
| :--- | :---: | :---: | :---: |
| **View Directory List (`/employees`)** | Full (All Departments) | Scoped to Assigned Dept | ❌ Forbidden (HTTP 403) |
| **View Individual Profile (`/employees/<id>`)** | Any Employee | Same Dept Only | Own Profile Only |
| **Add New Employee (`/employees/create`)** | ✅ Allowed | ❌ Forbidden (HTTP 403) | ❌ Forbidden (HTTP 403) |
| **Edit Employee (`/employees/<id>/edit`)** | ✅ Allowed | ❌ Forbidden (HTTP 403) | ❌ Forbidden (HTTP 403) |
| **Delete Employee (`/employees/<id>/delete`)** | ✅ Allowed (with Confirmation) | ❌ Forbidden (HTTP 403) | ❌ Forbidden (HTTP 403) |

#### Features & Validations:
- **Unique Employee ID**: Strictly enforced unique employee codes (`EMP-XXXX`).
- **Unique Corporate Email**: Verified RFC email format with duplicate prevention.
- **Search & Filtering**: Real-time ILIKE query matching full name, employee ID, email, department dropdown, job title filter, and employment status (Active, On Leave, Terminated).
- **Relational Integrity**: Safe task unassignment and cascading cleanup upon confirmed employee deletion.
- **Bootstrap 5 UI**: Fully responsive table and cards, status pills, delete confirmation modal, and tabs for assigned tasks, attendance logs, and payroll disbursements.

---

### 10. Attendance Management Module Architecture & Rules

The Attendance Management Module (`/attendance`) provides automated workforce time tracking, absence handling, and formal leave workflows:

#### Key Capabilities:
1. **Self Check-in & Check-out**: Secure employee punch-clock preventing duplicate check-ins on the same day (`uq_employee_attendance_date`).
2. **Punctuality & Late Arrival Detection**: Automatic comparison against standard work shift start (09:30 AM), recording tardiness minutes and marking late arrival flags.
3. **Safe Absence Rule**: Active personnel without a check-in on the current day remain marked as "Pending Check-In" and are not falsely categorized as absent before the working day concludes.
4. **Leave Request Workflow**: Comprehensive application process with date overlap validation, status tracking (Pending, Approved, Rejected), and managerial review with notes.
5. **Automatic Attendance Syncing**: Approving a leave application automatically provisions corresponding `on_leave` attendance calendar entries across the date span.
6. **Executive Reporting & Analytics**:
   - **Daily Attendance Report**: Live roster with status filtering, department breakdown, and workforce headcounts.
   - **Monthly Performance Report**: Working days evaluation, present/late/leave/absent counts, total work hours, and punctuality percentages.
   - **Late Arrival Incident Report**: Date-range filtered tardiness logs with cumulative lost minutes tracking.

---

### 11. Run Automated Test Suites

Run the 85 comprehensive automated unit tests covering Authentication, Admin Dashboard, Employee Management, Department Management, and Attendance Management:

```bash
python -m unittest discover tests
```

---

## ☁️ Render Deployment Guide

This project is pre-configured for seamless, zero-downtime production deployment to **[Render](https://render.com)**.

### Method 1: Turnkey Deployment via Render Blueprint (Recommended)

1. Push your repository to GitHub.
2. In the Render Dashboard, click **New +** -> **Blueprint**.
3. Connect your repository. Render will automatically parse [render.yaml](file:///c:/Users/Ammar%20Computer/Desktop/Company_managment_system/render.yaml) and configure:
   - **PostgreSQL Database**: Free managed PostgreSQL 18 instance with `company_management` database.
   - **Web Service**: Gunicorn WSGI web service connected directly to the database.
   - **Automatic Secret Generation**: Cryptographically secure 64-character `SECRET_KEY`.
   - **Database Migrations**: Automatically runs `flask db upgrade` during build.
4. Click **Apply**. Render handles provisioning and live deployment.

---

### Method 2: Manual Web Service Setup on Render

#### Step 1: Create a PostgreSQL Database on Render
1. In Render Dashboard, click **New +** -> **PostgreSQL**.
2. Set Database Name: `company_management`, User: `postgres`.
3. Once provisioned, copy the **Internal Database URL** (e.g., `postgresql://user:pass@dpg-xxx.oregon-postgres.render.com/company_management`).

#### Step 2: Create the Web Service
1. In Render Dashboard, click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the service settings:
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && flask db upgrade
     ```
   - **Start Command**:
     ```bash
     gunicorn -c gunicorn_config.py wsgi:app
     ```
   - **Plan**: `Free` or higher.

#### Step 3: Configure Production Environment Variables
In the Render Service **Environment** tab, set:

| Key | Value | Description |
| :--- | :--- | :--- |
| `FLASK_ENV` | `production` | Forces production mode (`DEBUG = False`, CSRF enabled) |
| `SECRET_KEY` | *(Generate via `python -c "import secrets; print(secrets.token_hex(32))"`)* | Cryptographic session signing & CSRF |
| `DATABASE_URL` | *(Paste the PostgreSQL connection URL from Step 1)* | Database connection string (driver auto-normalized to `postgresql+psycopg`) |

#### Step 4: Deploy & Initialize Initial Administrator
1. Click **Deploy Web Service**.
2. Once the deploy succeeds, visit your Render URL (e.g. `https://your-app.onrender.com`).
3. If no users exist in the database, the system will prompt you to create the initial Administrator account, or you can run via Render Shell:
   ```bash
   flask init-admin-env
   ```

---

## 🔒 Security & Best Practices Implemented
- **No Hardcoded Secrets**: All passwords, API keys, and connection strings originate from environment variables via `python-dotenv`.
- **Production Debug Safety**: Production mode strictly forces `DEBUG = False` and `TESTING = False`, preventing interactive debuggers or stack trace exposure.
- **CSRF Protection**: Universal Flask-WTF CSRF protection active on all POST forms with token rotation.
- **Password Hashing**: Passwords stored via Werkzeug PBKDF2/scrypt cryptographic hashing with unique salts.
- **Role-Based Access Control (RBAC)**: Strict permission enforcement protecting administrative routes from unauthorized Manager and Employee access.
- **SQL Injection Prevention**: Flask-SQLAlchemy with parameterized queries exclusively.
- **Strict PostgreSQL Engine Pool**: Configured with `pool_pre_ping=True`, `pool_recycle=300`, and `connect_timeout=15` to prevent stale connection drops on cloud platforms.
- **Error Handlers**: Custom 403, 404, and 500 error templates with automatic transaction rollback to prevent orphaned DB states.

---

## 📋 System Modules Summary

- [x] **Module 1: Core Architecture**: Flask Blueprints, PostgreSQL configuration, initial models, responsive UI, and live database connection diagnostics.
- [x] **Module 2: Authentication System**: Flask-Login sessions, secure password hashing, role-based access control (Admin, Manager, Employee), and Admin-only user provisioning.
- [x] **Module 3: Executive Admin Dashboard**: Real-time PostgreSQL KPIs, responsive Chart.js analytics, recent activity logs, and functional operational submodules.
- [x] **Module 4: Employee Management Module**: Add, Edit, Delete with modal confirmation, Search by name/EMP-ID, Department & Job title filtering, detailed profiles, role scoping.
- [x] **Module 5: Department Management Module**: Create, Edit, Delete with accidental deletion guard, Assign Department Manager, Allocate/Reassign/Remove staff, Department-wise metrics.
- [x] **Module 6: Attendance & Leave Management Module**: Employee self check-in/out, late arrival tracking > 9:30 AM, safe absence handling, leave request submission & approval with auto-attendance sync, daily/monthly/late reports.
- [x] **Module 7: Salary & Payroll Management Module**: Basic salary configuration, bonus and deduction ledger, Net Salary = Basic + Bonus - Deductions, batch generation, printable salary slips, and CSV export.
- [x] **Module 8: Task Management Module**: Priority and deadline assignment, kanban workflow transitions, overdue task detection, and department scoping.
- [x] **Module 9: Executive Reports Module**: 6 distinct reporting suites (Employees, Departments, Attendance, Payroll, Leaves, Tasks) with date filters, print stylesheets, and CSV downloads.
- [x] **Module 10: Dedicated User Dashboards**: Tailored role-specific home dashboards for Admin (`/admin/dashboard`), Manager (`/manager/dashboard`), and Employee (`/employee/dashboard`).

