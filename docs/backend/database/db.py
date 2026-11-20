import sqlite3
from pathlib import Path
from config import DB_PATH

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        # Upgrade databases created by earlier project versions.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "role" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user' "
                "CHECK(role IN ('user','admin'))"
            )
        if "is_active" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1 "
                "CHECK(is_active IN (0,1))"
            )

        # Upgrade existing settings tables safely; existing user preferences remain intact.
        settings_columns = {row["name"] for row in conn.execute("PRAGMA table_info(user_settings)")}
        if "expenditure_reminder" not in settings_columns:
            conn.execute("ALTER TABLE user_settings ADD COLUMN expenditure_reminder INTEGER NOT NULL DEFAULT 1")
        if "last_reminder_date" not in settings_columns:
            conn.execute("ALTER TABLE user_settings ADD COLUMN last_reminder_date TEXT")
        if "last_open_month" not in settings_columns:
            conn.execute("ALTER TABLE user_settings ADD COLUMN last_open_month TEXT")
