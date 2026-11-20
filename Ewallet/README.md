# Personal Finance Wallet Management

A personal finance ledger built with HTML5, CSS3, Vanilla JavaScript, Python Flask REST APIs, and SQLite. It is for tracking only; it does not execute real-money transfers through GCash, Maya, or banks.

## Run locally (Windows PowerShell)
From this project root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python run.py
```

Open **http://127.0.0.1:5000**. The database schema is in `backend/database/schema.sql`; the SQLite database is stored at `backend/instance/finance.db`.

## Configuration
Copy `.env.example` values into `.env` and set a strong random `SECRET_KEY`. For a deployment, generate and persist a Fernet `VAULT_KEY`; losing that key means encrypted vault entries cannot be recovered. Never commit `.env`, database backups, or vault keys.

## Project layout
- `frontend/`: HTML pages, shared components, styles, JavaScript modules, images and icons.
- `backend/`: Flask entry point, REST routes, SQLite schema, models, services, middleware, utilities and tests.
- `docs/`: project overview, architecture, database design, API reference and installation guide.

See `docs/` for additional documentation.


## Administrator account setup

The system does not ship with a hard-coded administrator username or password. Create your own administrator account from the backend folder:

```bash
cd backend
python create_admin.py
```

Enter an email address, full name, and a strong password (at least 12 characters). The password is entered privately and stored as a Werkzeug password hash. Then start the application as usual and sign in using the normal login page. Open `http://127.0.0.1:5000/admin.html` to use the administrator control center.

Administrator capabilities currently include viewing system totals and registered users, enabling/disabling regular user accounts, and deleting regular user accounts. Deleting a user also deletes that user's associated finance data. Administrators cannot disable or delete their own account, and the last active administrator is protected from deletion.

Existing databases are upgraded automatically when the app starts. New public registrations are always regular user accounts; administrator privileges can only be assigned through the local bootstrap script.


## User settings updates

The user dashboard Settings page now includes:

- **General:** daily expenditure reminder toggle and automatic monthly balance carry-forward notice.
- **Display:** Light, Dark, or System theme; English or Tagalog language; date and decimal display preferences.
- **Daily reminder:** when enabled, the backend creates one in-app reminder per calendar day when the user first opens the app.
- **Monthly carry-forward:** the wallet balance is a cumulative ledger balance, so it naturally carries into the next month. On the first app open of a new month, the backend records the month transition and creates a notification. It does not reset, duplicate, or create artificial transactions.

Existing SQLite databases are upgraded automatically when the Flask app starts. Existing users' financial records and settings are preserved.

## Notifications
Daily reminders and new-month balance notices appear under the bell icon in the top bar (a red badge counts unread items). Opening the bell marks them as read. The dashboard's Total balance card shows how much was carried over from the previous month.


## Parallel and Distributed Computing demonstration

See [`docs/PDC-GUIDE.md`](docs/PDC-GUIDE.md) for the process-based parallel financial report generator, administrator dashboard, API endpoints, and benchmarking methodology. This demonstrates parallel processing on one host; it is not a multi-machine distributed deployment.
