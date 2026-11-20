# System architecture
Browser pages are served by Flask from `frontend/`. Vanilla JavaScript calls JSON REST endpoints under `/api`. Flask routes use SQLite through the database module. Passwords are hashed with Werkzeug and password-vault secrets are encrypted with Fernet.
