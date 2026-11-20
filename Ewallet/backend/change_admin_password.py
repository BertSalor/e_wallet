
from getpass import getpass
from werkzeug.security import generate_password_hash
from database.db import connect


def main():
    print("\n===================================")
    print("       ADMIN PASSWORD RESET")
    print("===================================\n")

    email = input("Enter Admin Email: ").strip().lower()

    if not email:
        print("Email is required.")
        return

    new_password = getpass("Enter New Password: ")
    confirm_password = getpass("Confirm New Password: ")

    if len(new_password) < 8:
        print("Password must be at least 8 characters.")
        return

    if new_password != confirm_password:
        print("Passwords do not match.")
        return

    conn = connect()

    try:
        admin = conn.execute(
            """
            SELECT id, email, role, is_active
            FROM users
            WHERE email = ? COLLATE NOCASE
              AND role = 'admin'
            """,
            (email,)
        ).fetchone()

        if admin is None:
            print("\nAdmin account not found.")
            return

        if not admin["is_active"]:
            print("\nThis admin account is inactive.")
            return

        password_hash = generate_password_hash(new_password)

        conn.execute(
            """
            UPDATE users
            SET password_hash = ?
            WHERE id = ?
            """,
            (password_hash, admin["id"])
        )

        conn.commit()

        print("\n===================================")
        print(" ADMIN PASSWORD CHANGED SUCCESSFULLY")
        print("===================================")
        print("Admin Email:", admin["email"])
        print("You can now log in using your new password.")

    except Exception as error:
        conn.rollback()
        print("\nError:", error)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
