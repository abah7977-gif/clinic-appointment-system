# Clinic Appointment System V3

Responsive clinic appointment and queue-management system prepared for web deployment and future Android/iPhone apps.

## Features
- Secure login with Admin, Receptionist and Doctor roles
- Patient registration, search and appointment history
- Doctor management, room assignment, weekly schedule, leave/unavailable dates
- New appointment and rescheduling
- Auto-assign available doctor based on schedule, leave, overlap and workload
- Queue number, check-in, call, start consultation, complete, cancel and no-show
- Waiting-time and consultation-time metrics
- Live queue board
- Dashboard charts and daily KPIs
- SQLite for local testing
- PostgreSQL/Supabase-ready through DATABASE_URL

## Demo Accounts
Admin: admin / admin123
Receptionist: receptionist / reception123
Doctor: doctor1 / doctor123

Change all demo passwords before using real patient information.

## Run Locally
1. Install Python 3.11 or newer.
2. Extract the ZIP and open Terminal/Command Prompt in the project folder.
3. Create environment: `python -m venv .venv`
4. Windows activation: `.venv\\Scripts\\activate`
5. macOS/Linux activation: `source .venv/bin/activate`
6. Install: `pip install -r requirements.txt`
7. Copy `.env.example` to `.env`
8. Run: `python app.py`
9. Open: `http://127.0.0.1:5000`

## PostgreSQL / Supabase
Set DATABASE_URL to your PostgreSQL connection string, for example:
`postgresql+psycopg://USER:PASSWORD@HOST:5432/postgres`

## Important Production Notes
Before real patient data is used, enable HTTPS, strong passwords, audit logging, backups, role-based access review, and applicable privacy/data-protection controls.

## Suggested V4
- REST API
- PWA installability
- Android/iPhone shell
- reminders/notifications
- patient self-booking
- export to Excel/PDF
- audit trail
- multi-clinic support
