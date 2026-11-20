
from getpass import getpass
from werkzeug.security import generate_password_hash
from database.db import connect, init_db
import re


def main():
    init_db()
    print("\n================================")
    print("       CREATE ADMIN ACCOUNT")
    print("================================\n")

    email = input("Admin Email: ").strip().lower()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Invalid email address.")
        return

    password = getpass("Admin Password: ")
    confirm = getpass("Confirm Password: ")

    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return

    if password != confirm:
        print("Passwords do not match.")
        return

    conn = connect()

    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing:
            admin_id = existing["id"] if hasattr(existing, "keys") else existing[0]
            conn.execute(
                "UPDATE users SET password_hash=?, role='admin', is_active=1 WHERE id=?",
                (generate_password_hash(password), admin_id)
            )
            conn.execute(
                "INSERT OR IGNORE INTO user_profiles (user_id, full_name) VALUES (?, ?)",
                (admin_id, "Administrator")
            )
            action = "updated and promoted to administrator"
        else:
            cursor = conn.execute(
                """
                INSERT INTO users (email, password_hash, role, is_active)
                VALUES (?, ?, 'admin', 1)
                """,
                (email, generate_password_hash(password))
            )
            admin_id = cursor.lastrowid
            conn.execute(
                "INSERT INTO user_profiles (user_id, full_name) VALUES (?, ?)",
                (admin_id, "Administrator")
            )
            action = "created successfully"

        conn.commit()

        print(f"\\nAdmin account {action}!")
        print("Admin Email:", email)
        print("Role: admin")

    except Exception as error:
        conn.rollback()
        print("Error:", error)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
