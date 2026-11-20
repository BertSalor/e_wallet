BLUEWALLET — COMPLETE SOURCE WITH ADMIN-ONLY DASHBOARD UPGRADE

This archive contains the full E_wallet application source plus the administrator
console upgrade. It intentionally excludes your local virtual environment, live
SQLite database, vault.key, and .env secrets. Keep those files from your existing
installation; do not overwrite or publish them.

ADMIN SIDEBAR
1. Dashboard
2. User Management
3. Account & Wallet Management
4. Transaction Management
5. Categories Management
6. Reports & Analytics
7. Notifications & Announcements
8. Activity Logs
9. System Settings
10. Database & Backup
11. Security Management
12. Logout

WHAT IS IMPLEMENTED
- System overview with users, accounts, transaction totals, income/expense totals,
  recent transactions, and a monthly income/expense chart.
- User search/filter, profile name/email editing, enable/disable, and deletion.
- Account and wallet monitoring (read-only; no wallet balances are changed).
- Transaction search and filters by type and date, plus CSV export.
- Category creation, editing, and deletion safeguards for categories already used.
- Date-range report summary and CSV transaction export.
- Announcements delivered to all active users or a selected user through the existing
  in-app notifications table.
- Administrator activity log.
- Separate admin settings storage.
- SQLite backup creation, listing, download, validated restore, and pre-restore safety
  backup.
- Administrator account listing, granting admin access to an existing user, and
  revoking admin access with last-admin protections.

IMPORTANT SCOPE / LIMITATIONS
- Only admin.html, new admin CSS/JS, new admin API module, and the Flask app factory
  integration are changed for this upgrade. Existing user pages and financial logic
  are retained.
- The registration_enabled and maintenance_mode values are saved as admin settings
  only. They are NOT wired into the existing registration or user routes because
  this is an admin-only change and those routes must remain untouched.
- Reports export CSV. Native PDF/Excel export is not included.
- Wallet/account management is monitoring-only. No real-money transfers or wallet
  balance editing are provided.
- Deleting a user deletes that user's associated records through the existing SQLite
  foreign-key cascade. Confirm carefully before using it.
- Database restore replaces the live database. A safety backup is created first.
- The security page changes administrator role assignments. Granting admin access
  to an existing user also sets the password entered on that form as a temporary
  password; communicate it securely and have the user change it after sign-in.

INSTALL ON YOUR EXISTING WINDOWS PROJECT
1. Stop the Flask server.
2. Back up the entire existing E_wallet folder, especially:
   backend/instance/finance.db
   backend/instance/vault.key
   .env
3. Extract this archive.
4. Copy the E_wallet folder from the archive into your existing project folder.
   Allow replacement only for the files included in this archive. Your local
   finance.db, vault.key, .env, and .venv are not included and should remain untouched.
5. Open PowerShell in the existing project folder.
6. Activate your existing environment, or create one if needed:
   .venv\Scripts\Activate.ps1
   python -m pip install -r backend/requirements.txt
7. Start the app using the existing command:
   python run.py
   (If you normally start from backend, use: cd backend; python run.py)
8. Sign in with an account whose users.role is 'admin'.
9. Open http://127.0.0.1:5000/admin.html

CREATE AN ADMIN ACCOUNT IF NEEDED
From the backend folder, run:
   python create_admin.py
Use a valid email and a password of at least 8 characters. The script creates a
separate administrator account; it does not change existing user accounts.

FILES CHANGED / ADDED BY THE ADMIN UPGRADE
- frontend/admin.html (admin page only)
- frontend/assets/css/admin.css (new admin-only stylesheet)
- frontend/assets/js/admin.js (new admin-only page logic)
- backend/legacy_app/admin_routes.py (new admin-only API blueprint)
- backend/legacy_app/__init__.py (registers the admin blueprint and additive admin tables)

VALIDATION
Python syntax compilation and JavaScript syntax checking are performed on the source.
A full live Flask/database browser test must be completed in the user's local
environment because the execution environment used to prepare this archive does
not have the project's Flask dependencies available and cannot download packages.
