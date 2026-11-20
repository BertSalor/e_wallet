from flask import Blueprint, request, jsonify, session, g
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet, InvalidToken
from datetime import date
from calendar import monthrange
import secrets, sqlite3, os
from .db import connect
from config import VAULT_KEY

api = Blueprint("api", __name__)
fernet = Fernet(VAULT_KEY.encode() if isinstance(VAULT_KEY, str) else VAULT_KEY)


def ok(data=None, status=200, **extra):
    payload = {"success": True, "data": data}
    payload.update(extra)
    return jsonify(payload), status


def fail(message, status=400):
    return jsonify({"success": False, "error": message}), status


def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@api.teardown_request
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return fail("Please log in to continue.", 401)
        return fn(*args, **kwargs)

    return wrapped


def payload():
    return request.get_json(silent=True) or {}


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return fail("Please log in to continue.", 401)
        row = db().execute(
            "SELECT role,is_active FROM users WHERE id=?", (session["user_id"],)
        ).fetchone()
        if not row or not row["is_active"]:
            session.clear()
            return fail("This account is unavailable.", 403)
        if row["role"] != "admin":
            return fail("Administrator access is required.", 403)
        return fn(*args, **kwargs)
    return wrapped


def user_id():
    return session["user_id"]


def owned(sql, params=()):
    return db().execute(sql, (user_id(), *params))


def money(v):
    try:
        n = round(float(v), 2)
    except (TypeError, ValueError):
        raise ValueError("Amount must be a valid number.")
    if n <= 0:
        raise ValueError("Amount must be greater than zero.")
    return n


def seed_user(uid):
    defaults = [
        ("Salary", "income", "briefcase", "#16a085"),
        ("Freelance", "income", "laptop", "#3498db"),
        ("Gift", "income", "gift", "#9b59b6"),
        ("Food & Beverage", "expense", "utensils", "#e67e22"),
        ("Transportation", "expense", "car", "#2980b9"),
        ("Home", "expense", "house", "#8e44ad"),
        ("Market", "expense", "shopping-cart", "#27ae60"),
        ("Health Care", "expense", "heart-pulse", "#e74c3c"),
        ("Entertainment", "expense", "film", "#f1c40f"),
        ("Others", "expense", "tag", "#607d8b"),
    ]
    for name, kind, icon, color in defaults:
        db().execute(
            "INSERT OR IGNORE INTO categories(user_id,name,kind,icon,color,is_default) VALUES(?,?,?,?,?,1)",
            (uid, name, kind, icon, color),
        )
    db().execute(
        "INSERT OR IGNORE INTO accounts(user_id,name,kind,opening_balance) VALUES(?,?,?,?)",
        (uid, "Cash Wallet", "Cash", 0),
    )
    db().execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES(?)", (uid,))


@api.get("/admin/overview")
@admin_required
def admin_overview():
    users = db().execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    active = db().execute("SELECT COUNT(*) n FROM users WHERE is_active=1").fetchone()["n"]
    transactions = db().execute("SELECT COUNT(*) n FROM transactions").fetchone()["n"]
    volume = db().execute("SELECT COALESCE(SUM(amount),0) n FROM transactions").fetchone()["n"]
    return ok({"total_users": users, "active_users": active,
               "total_transactions": transactions, "transaction_volume": round(volume, 2)})


@api.get("/admin/users")
@admin_required
def admin_users():
    rows = db().execute(
        """SELECT u.id,u.email,u.role,u.is_active,u.created_at,
                  COALESCE(p.full_name,'') full_name,
                  (SELECT COUNT(*) FROM transactions t WHERE t.user_id=u.id) transaction_count
           FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id
           ORDER BY u.created_at DESC,u.id DESC"""
    ).fetchall()
    return ok([dict(row) for row in rows])


@api.patch("/admin/users/<int:uid>/status")
@admin_required
def admin_user_status(uid):
    if uid == user_id():
        return fail("You cannot disable your own administrator account.")
    target = db().execute("SELECT id,role FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        return fail("User not found.", 404)
    active = payload().get("is_active")
    if active not in (True, False, 0, 1):
        return fail("Provide a valid account status.")
    db().execute("UPDATE users SET is_active=? WHERE id=?", (int(bool(active)), uid))
    db().commit()
    return ok({"updated": True, "is_active": int(bool(active))})


@api.delete("/admin/users/<int:uid>")
@admin_required
def admin_delete_user(uid):
    if uid == user_id():
        return fail("You cannot delete your own administrator account.")
    target = db().execute("SELECT id,role FROM users WHERE id=?", (uid,)).fetchone()
    if not target:
        return fail("User not found.", 404)
    if target["role"] == "admin":
        admins = db().execute("SELECT COUNT(*) n FROM users WHERE role='admin' AND is_active=1").fetchone()["n"]
        if admins <= 1:
            return fail("The last active administrator cannot be deleted.")
    db().execute("DELETE FROM users WHERE id=?", (uid,))
    db().commit()
    return ok({"deleted": True})


@api.get("/health")
def health():
    return ok({"status": "online"})


@api.post("/auth/register")
def register():
    p = payload()
    email = str(p.get("email", "")).strip().lower()
    password = str(p.get("password", ""))
    name = str(p.get("name", "")).strip()
    if not name or len(name) > 100:
        return fail("Enter your name (up to 100 characters).")
    if "@" not in email or len(email) > 180:
        return fail("Enter a valid email address.")
    if len(password) < 8:
        return fail("Password must contain at least 8 characters.")
    try:
        cur = db().execute(
            "INSERT INTO users(email,password_hash) VALUES(?,?)",
            (email, generate_password_hash(password)),
        )
        uid = cur.lastrowid
        db().execute(
            "INSERT INTO user_profiles(user_id,full_name) VALUES(?,?)", (uid, name)
        )
        seed_user(uid)
        db().commit()
        session.clear()
        session["user_id"] = uid
        session["csrf"] = secrets.token_urlsafe(24)
        return ok(
            {"id": uid, "email": email, "name": name, "csrf": session["csrf"]}, 201
        )
    except sqlite3.IntegrityError:
        return fail("An account with this email already exists.", 409)


@api.post("/auth/login")
def login():
    p = payload()
    email = str(p.get("email", "")).strip().lower()
    password = str(p.get("password", ""))
    row = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return fail("Incorrect email or password.", 401)
    if not row["is_active"]:
        return fail("This account has been disabled. Contact the administrator.", 403)
    session.clear()
    session["user_id"] = row["id"]
    session["csrf"] = secrets.token_urlsafe(24)
    profile = (
        db()
        .execute("SELECT full_name FROM user_profiles WHERE user_id=?", (row["id"],))
        .fetchone()
    )
    return ok(
        {
            "id": row["id"],
            "email": email,
            "name": profile["full_name"] if profile else "",
            "role": row["role"],
            "csrf": session["csrf"],
        }
    )


@api.post("/auth/logout")
@login_required
def logout():
    session.clear()
    return ok({"message": "Logged out."})


def process_user_open_events(uid):
    """Create idempotent daily and monthly in-app reminders on the user's first app open."""
    today = date.today().isoformat()
    current_month = today[:7]
    row = db().execute(
        "SELECT expenditure_reminder,last_reminder_date,last_open_month FROM user_settings WHERE user_id=?",
        (uid,),
    ).fetchone()
    if not row:
        db().execute("INSERT OR IGNORE INTO user_settings(user_id) VALUES(?)", (uid,))
        row = db().execute(
            "SELECT expenditure_reminder,last_reminder_date,last_open_month FROM user_settings WHERE user_id=?",
            (uid,),
        ).fetchone()

    # The account balance is a lifetime ledger total, so it already carries forward.
    # Record the month transition and notify once; never reset or duplicate money.
    previous_month = row["last_open_month"]
    if previous_month and previous_month != current_month:
        db().execute(
            "INSERT INTO notifications(user_id,title,body) VALUES(?,?,?)",
            (uid, "New month balance updated",
             "Your wallet balance has carried forward from the previous month. Review your new month's spending."),
        )
    if not previous_month:
        db().execute(
            "UPDATE user_settings SET last_open_month=? WHERE user_id=?",
            (current_month, uid),
        )
    elif previous_month != current_month:
        db().execute(
            "UPDATE user_settings SET last_open_month=? WHERE user_id=?",
            (current_month, uid),
        )

    if row["expenditure_reminder"] and row["last_reminder_date"] != today:
        db().execute(
            "INSERT INTO notifications(user_id,title,body) VALUES(?,?,?)",
            (uid, "Daily expenditure reminder",
             "Remember to record today's expenses and review your spending."),
        )
        db().execute(
            "UPDATE user_settings SET last_reminder_date=? WHERE user_id=?",
            (today, uid),
        )
    db().commit()


@api.get("/auth/me")
def me():
    if not session.get("user_id"):
        return ok({"authenticated": False})
    process_user_open_events(user_id())
    row = owned(
        "SELECT u.id,u.email,u.role,p.full_name,s.theme,s.currency,s.date_format,s.decimal_separator,s.language FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id LEFT JOIN user_settings s ON s.user_id=u.id WHERE u.id=?"
    ).fetchone()
    return ok(
        {"authenticated": True, "user": dict(row), "csrf": session.get("csrf", "")}
    )


@api.get("/dashboard")
@login_required
def dashboard():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    sums = owned(
        "SELECT kind,COALESCE(SUM(amount),0) total FROM transactions WHERE user_id=? AND substr(transaction_date,1,7)=? AND kind IN ('income','expense') GROUP BY kind",
        (month,),
    ).fetchall()
    totals = {r["kind"]: r["total"] for r in sums}
    income = totals.get("income", 0)
    expense = totals.get("expense", 0)
    opening = owned(
        "SELECT COALESCE(SUM(opening_balance),0) n FROM accounts WHERE user_id=?"
    ).fetchone()["n"]
    allsum = owned(
        "SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount WHEN kind='expense' THEN -amount ELSE 0 END),0) n FROM transactions WHERE user_id=?"
    ).fetchone()["n"]
    prior = owned(
        "SELECT COALESCE(SUM(CASE WHEN kind='income' THEN amount WHEN kind='expense' THEN -amount ELSE 0 END),0) n FROM transactions WHERE user_id=? AND transaction_date < ?",
        (month + "-01",),
    ).fetchone()["n"]
    recent = owned(
        "SELECT t.*,c.name category,c.color FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.user_id=? ORDER BY transaction_date DESC,t.id DESC LIMIT 8"
    ).fetchall()
    bycat = (
        db()
        .execute(
            "SELECT c.name,c.color,COALESCE(SUM(t.amount),0) total FROM categories c LEFT JOIN transactions t ON t.category_id=c.id AND t.user_id=c.user_id AND t.kind='expense' AND substr(t.transaction_date,1,7)=? WHERE c.user_id=? AND c.kind='expense' GROUP BY c.id ORDER BY total DESC",
            (month, user_id()),
        )
        .fetchall()
    )
    return ok(
        {
            "month": month,
            "balance": round(opening + allsum, 2),
            "carried_forward": round(opening + prior, 2),
            "income": income,
            "expense": expense,
            "savings": income - expense,
            "recent": [dict(r) for r in recent],
            "categories": [dict(r) for r in bycat],
        }
    )


@api.get("/accounts")
@login_required
def accounts():
    rows = owned(
        "SELECT a.*,a.opening_balance+COALESCE((SELECT SUM(CASE WHEN t.kind='income' THEN t.amount WHEN t.kind='expense' THEN -t.amount ELSE 0 END) FROM transactions t WHERE t.account_id=a.id),0) balance FROM accounts a WHERE a.user_id=? ORDER BY a.id"
    ).fetchall()
    return ok([dict(r) for r in rows])


@api.post("/accounts")
@login_required
def create_account():
    p = payload()
    name = str(p.get("name", "")).strip()
    if not name:
        return fail("Account name is required.")
    try:
        amount = round(float(p.get("opening_balance", 0)), 2)
    except:
        return fail("Opening balance must be numeric.")
    try:
        cur = db().execute(
            "INSERT INTO accounts(user_id,name,kind,opening_balance) VALUES(?,?,?,?)",
            (user_id(), name, p.get("kind", "Cash"), amount),
        )
        db().commit()
        return ok({"id": cur.lastrowid}, 201)
    except sqlite3.IntegrityError:
        return fail("An account with this name already exists.", 409)


@api.get("/categories")
@login_required
def categories():
    return ok(
        [
            dict(r)
            for r in owned(
                "SELECT * FROM categories WHERE user_id=? ORDER BY kind,name"
            ).fetchall()
        ]
    )


@api.post("/categories")
@login_required
def create_category():
    p = payload()
    name = str(p.get("name", "")).strip()
    kind = p.get("kind")
    if not name or kind not in ("income", "expense"):
        return fail("Provide a category name and valid type.")
    try:
        cur = db().execute(
            "INSERT INTO categories(user_id,name,kind,icon,color) VALUES(?,?,?,?,?)",
            (user_id(), name, kind, p.get("icon", "tag"), p.get("color", "#268bd2")),
        )
        db().commit()
        return ok({"id": cur.lastrowid}, 201)
    except sqlite3.IntegrityError:
        return fail("That category already exists.", 409)


@api.route("/categories/<int:cid>", methods=["PUT", "DELETE"])
@login_required
def category_item(cid):
    row = owned("SELECT * FROM categories WHERE user_id=? AND id=?", (cid,)).fetchone()
    if not row:
        return fail("Category not found.", 404)
    if request.method == "DELETE":
        if row["is_default"]:
            return fail("Default categories cannot be deleted.")
        owned("DELETE FROM categories WHERE user_id=? AND id=?", (cid,))
        db().commit()
        return ok({"deleted": True})
    p = payload()
    db().execute(
        "UPDATE categories SET name=?,icon=?,color=? WHERE user_id=? AND id=?",
        (
            p.get("name", row["name"]),
            p.get("icon", row["icon"]),
            p.get("color", row["color"]),
            user_id(),
            cid,
        ),
    )
    db().commit()
    return ok({"updated": True})


@api.get("/transactions")
@login_required
def transactions():
    where = []
    params = []
    for key, col in [
        ("kind", "t.kind"),
        ("from", "t.transaction_date"),
        ("to", "t.transaction_date"),
        ("category_id", "t.category_id"),
    ]:
        val = request.args.get(key)
        if val:
            where.append(
                f"{col} "
                + (">=" if key == "from" else "<=" if key == "to" else "=")
                + " ?"
            )
            params.append(val)
    q = request.args.get("q", "").strip()
    if q:
        where.append("(t.note LIKE ? OR c.name LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    sql = "SELECT t.*,c.name category,c.color,a.name account FROM transactions t LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN accounts a ON a.id=t.account_id WHERE t.user_id=?"
    if where:
        sql += " AND " + " AND ".join(where)
    sql += " ORDER BY t.transaction_date DESC,t.id DESC"
    rows = db().execute(sql, (user_id(), *params)).fetchall()
    return ok([dict(r) for r in rows])


@api.post("/transactions")
@login_required
def create_transaction():
    p = payload()
    kind = p.get("kind")
    note = str(p.get("note", ""))[:500]
    d = p.get("transaction_date") or date.today().isoformat()
    if kind not in ("income", "expense", "transfer"):
        return fail("Invalid transaction type.")
    try:
        amount = money(p.get("amount"))
    except ValueError as e:
        return fail(str(e))
    account_id = p.get("account_id")
    if (
        account_id
        and not owned(
            "SELECT id FROM accounts WHERE user_id=? AND id=?", (account_id,)
        ).fetchone()
    ):
        return fail("Invalid account.")
    cat = p.get("category_id")
    if kind != "transfer" and (
        not cat
        or not owned(
            "SELECT id FROM categories WHERE user_id=? AND id=? AND kind=?", (cat, kind)
        ).fetchone()
    ):
        return fail("Choose a valid category.")
    if kind == "transfer":
        dest = p.get("destination", "")
        if not dest:
            return fail("Enter a destination account or wallet.")
    cur = db().execute(
        "INSERT INTO transactions(user_id,account_id,category_id,kind,amount,note,transaction_date,destination) VALUES(?,?,?,?,?,?,?,?)",
        (
            user_id(),
            account_id,
            cat if kind != "transfer" else None,
            kind,
            amount,
            note,
            d,
            str(p.get("destination", "")),
        ),
    )
    db().commit()
    return ok({"id": cur.lastrowid}, 201)


@api.route("/transactions/<int:tid>", methods=["PUT", "DELETE"])
@login_required
def transaction_item(tid):
    row = owned(
        "SELECT * FROM transactions WHERE user_id=? AND id=?", (tid,)
    ).fetchone()
    if not row:
        return fail("Transaction not found.", 404)
    if request.method == "DELETE":
        owned("DELETE FROM transactions WHERE user_id=? AND id=?", (tid,))
        db().commit()
        return ok({"deleted": True})
    p = payload()
    kind = p.get("kind", row["kind"])
    try:
        amount = money(p.get("amount", row["amount"]))
    except ValueError as e:
        return fail(str(e))
    if kind not in ("income", "expense", "transfer"):
        return fail("Invalid transaction type.")
    account_id = p.get("account_id", row["account_id"])
    if (
        account_id
        and not owned(
            "SELECT id FROM accounts WHERE user_id=? AND id=?", (account_id,)
        ).fetchone()
    ):
        return fail("Invalid account.")
    if kind == "transfer" and not str(p.get("destination", row["destination"]) or "").strip():
        return fail("Enter a destination account or wallet.")
    cat = p.get("category_id", row["category_id"])
    if kind != "transfer" and (
        not cat
        or not owned(
            "SELECT id FROM categories WHERE user_id=? AND id=? AND kind=?", (cat, kind)
        ).fetchone()
    ):
        return fail("Choose a valid category.")
    db().execute(
        "UPDATE transactions SET kind=?,amount=?,note=?,transaction_date=?,category_id=?,account_id=?,destination=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND id=?",
        (
            kind,
            amount,
            str(p.get("note", row["note"]))[:500],
            p.get("transaction_date", row["transaction_date"]),
            cat if kind != "transfer" else None,
            account_id,
            p.get("destination", row["destination"]),
            user_id(),
            tid,
        ),
    )
    db().commit()
    return ok({"updated": True})


@api.get("/calendar")
@login_required
def calendar_data():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    rows = owned(
        "SELECT transaction_date,kind,SUM(amount) total,COUNT(*) count FROM transactions WHERE user_id=? AND substr(transaction_date,1,7)=? GROUP BY transaction_date,kind ORDER BY transaction_date",
        (month,),
    ).fetchall()
    return ok([dict(r) for r in rows])


@api.get("/budgets")
@login_required
def budgets():
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    rows = owned(
        "SELECT b.*,c.name category,c.color,COALESCE((SELECT SUM(t.amount) FROM transactions t WHERE t.user_id=b.user_id AND t.category_id=b.category_id AND t.kind='expense' AND substr(t.transaction_date,1,7)=b.month),0) spent FROM budgets b LEFT JOIN categories c ON c.id=b.category_id WHERE b.user_id=? AND b.month=? ORDER BY c.name",
        (month,),
    ).fetchall()
    return ok([dict(r) for r in rows])


@api.post("/budgets")
@login_required
def save_budget():
    p = payload()
    cat = p.get("category_id")
    month = p.get("month", date.today().strftime("%Y-%m"))
    try:
        amount = round(float(p.get("amount")), 2)
    except:
        return fail("Enter a valid budget amount.")
    if (
        amount < 0
        or not owned(
            "SELECT id FROM categories WHERE user_id=? AND id=? AND kind='expense'",
            (cat,),
        ).fetchone()
    ):
        return fail("Choose an expense category and non-negative amount.")
    db().execute(
        "INSERT INTO budgets(user_id,category_id,month,amount) VALUES(?,?,?,?) ON CONFLICT(user_id,category_id,month) DO UPDATE SET amount=excluded.amount",
        (user_id(), cat, month, amount),
    )
    db().commit()
    return ok({"saved": True}, 201)


@api.delete("/budgets/<int:bid>")
@login_required
def delete_budget(bid):
    cur = owned("DELETE FROM budgets WHERE user_id=? AND id=?", (bid,))
    db().commit()
    if not cur.rowcount:
        return fail("Budget not found.", 404)
    return ok({"deleted": True})


@api.get("/reports")
@login_required
def reports():
    start = request.args.get("from", "0001-01-01")
    end = request.args.get("to", "9999-12-31")
    rows = owned(
        "SELECT substr(transaction_date,1,7) month,kind,SUM(amount) total FROM transactions WHERE user_id=? AND transaction_date BETWEEN ? AND ? AND kind IN ('income','expense') GROUP BY month,kind ORDER BY month",
        (start, end),
    ).fetchall()
    cats = owned(
        "SELECT c.name,c.color,SUM(t.amount) total FROM transactions t JOIN categories c ON c.id=t.category_id AND c.user_id=t.user_id WHERE t.user_id=? AND t.kind='expense' AND t.transaction_date BETWEEN ? AND ? GROUP BY c.id ORDER BY total DESC",
        (start, end),
    ).fetchall()
    return ok(
        {"monthly": [dict(r) for r in rows], "categories": [dict(r) for r in cats]}
    )


@api.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    if request.method == "GET":
        q = request.args.get("q", "")
        rows = owned(
            "SELECT * FROM notes WHERE user_id=? AND (title LIKE ? OR body LIKE ?) ORDER BY pinned DESC,updated_at DESC",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        return ok([dict(r) for r in rows])
    p = payload()
    title = str(p.get("title", "")).strip()
    if not title:
        return fail("Note title is required.")
    cur = db().execute(
        "INSERT INTO notes(user_id,title,body,color,category,pinned) VALUES(?,?,?,?,?,?)",
        (
            user_id(),
            title,
            str(p.get("body", ""))[:10000],
            p.get("color", "#fff2a8"),
            p.get("category", "General"),
            int(bool(p.get("pinned"))),
        ),
    )
    db().commit()
    return ok({"id": cur.lastrowid}, 201)


@api.route("/notes/<int:nid>", methods=["PUT", "DELETE"])
@login_required
def note_item(nid):
    row = owned("SELECT * FROM notes WHERE user_id=? AND id=?", (nid,)).fetchone()
    if not row:
        return fail("Note not found.", 404)
    if request.method == "DELETE":
        owned("DELETE FROM notes WHERE user_id=? AND id=?", (nid,))
        db().commit()
        return ok({"deleted": True})
    p = payload()
    db().execute(
        "UPDATE notes SET title=?,body=?,color=?,category=?,pinned=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND id=?",
        (
            p.get("title", row["title"]),
            p.get("body", row["body"]),
            p.get("color", row["color"]),
            p.get("category", row["category"]),
            int(bool(p.get("pinned", row["pinned"]))),
            user_id(),
            nid,
        ),
    )
    db().commit()
    return ok({"updated": True})


@api.route("/vault", methods=["GET", "POST"])
@login_required
def vault():
    if request.method == "GET":
        rows = owned(
            "SELECT id,site,username,url,notes,created_at FROM password_vault WHERE user_id=? ORDER BY site"
        ).fetchall()
        return ok([dict(r) for r in rows])
    p = payload()
    site = str(p.get("site", "")).strip()
    password = str(p.get("password", ""))
    if not site or not password:
        return fail("Website and password are required.")
    token = fernet.encrypt(password.encode()).decode()
    cur = db().execute(
        "INSERT INTO password_vault(user_id,site,username,encrypted_password,url,notes) VALUES(?,?,?,?,?,?)",
        (
            user_id(),
            site,
            p.get("username", ""),
            token,
            p.get("url", ""),
            p.get("notes", ""),
        ),
    )
    db().commit()
    return ok({"id": cur.lastrowid}, 201)


@api.post("/vault/<int:vid>/reveal")
@login_required
def reveal_vault(vid):
    row = owned(
        "SELECT encrypted_password FROM password_vault WHERE user_id=? AND id=?", (vid,)
    ).fetchone()
    if not row:
        return fail("Vault entry not found.", 404)
    try:
        return ok(
            {"password": fernet.decrypt(row["encrypted_password"].encode()).decode()}
        )
    except InvalidToken:
        return fail("Unable to decrypt this entry. Check your VAULT_KEY.", 500)


@api.delete("/vault/<int:vid>")
@login_required
def delete_vault(vid):
    cur = owned("DELETE FROM password_vault WHERE user_id=? AND id=?", (vid,))
    db().commit()
    if not cur.rowcount:
        return fail("Vault entry not found.", 404)
    return ok({"deleted": True})


@api.get("/profile")
@login_required
def profile():
    row = owned(
        "SELECT u.email,p.full_name,p.currency FROM users u JOIN user_profiles p ON p.user_id=u.id WHERE u.id=?"
    ).fetchone()
    return ok(dict(row))


@api.put("/profile")
@login_required
def update_profile():
    p = payload()
    name = str(p.get("full_name", "")).strip()
    currency = p.get("currency", "PHP")
    if not name or len(name) > 100:
        return fail("Name is required (up to 100 characters).")
    if currency not in ("PHP", "USD", "EUR", "GBP", "JPY", "SGD"):
        return fail("Choose a supported currency.")
    db().execute(
        "UPDATE user_profiles SET full_name=?,currency=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
        (name, currency, user_id()),
    )
    db().execute(
        "UPDATE user_settings SET currency=? WHERE user_id=?", (currency, user_id())
    )
    db().commit()
    return ok({"updated": True})


@api.put("/auth/password")
@login_required
def change_password():
    p = payload()
    row = owned("SELECT password_hash FROM users WHERE id=?").fetchone()
    if not check_password_hash(
        row["password_hash"], str(p.get("current_password", ""))
    ):
        return fail("Current password is incorrect.", 401)
    new = str(p.get("new_password", ""))
    if len(new) < 8:
        return fail("New password must contain at least 8 characters.")
    db().execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (generate_password_hash(new), user_id()),
    )
    db().commit()
    return ok({"updated": True})


@api.route("/settings", methods=["GET", "PUT"])
@login_required
def settings():
    if request.method == "GET":
        process_user_open_events(user_id())
        return ok(dict(owned("SELECT * FROM user_settings WHERE user_id=?").fetchone()))

    p = payload()
    current = dict(owned("SELECT * FROM user_settings WHERE user_id=?").fetchone())
    values = {
        "theme": p.get("theme", current["theme"]),
        "currency": p.get("currency", current["currency"]),
        "date_format": p.get("date_format", current["date_format"]),
        "decimal_separator": p.get("decimal_separator", current["decimal_separator"]),
        "language": p.get("language", current["language"]),
        "expenditure_reminder": p.get("expenditure_reminder", current["expenditure_reminder"]),
    }
    if values["currency"] not in ("PHP", "USD", "EUR", "GBP", "JPY", "SGD"):
        return fail("Choose a supported currency.")
    if values["theme"] not in ("light", "dark", "system"):
        return fail("Invalid theme.")
    if values["language"] not in ("en", "tl"):
        return fail("Choose English or Tagalog.")
    if values["decimal_separator"] not in (".", ","):
        return fail("Invalid decimal separator.")
    if values["date_format"] not in ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"):
        return fail("Invalid date format.")
    reminder = values["expenditure_reminder"]
    if reminder in (True, 1, "1", "true", "on"):
        reminder = 1
    elif reminder in (False, 0, "0", "false", "off", None, ""):
        reminder = 0
    else:
        return fail("Invalid expenditure reminder setting.")

    db().execute(
        """UPDATE user_settings
           SET theme=?,currency=?,date_format=?,decimal_separator=?,language=?,
               expenditure_reminder=?
           WHERE user_id=?""",
        (values["theme"], values["currency"], values["date_format"],
         values["decimal_separator"], values["language"], reminder, user_id()),
    )
    db().commit()
    values["expenditure_reminder"] = reminder
    return ok(values)


@api.post("/notifications/read")
@login_required
def mark_notifications_read():
    owned("UPDATE notifications SET is_read=1 WHERE user_id=?", ())
    db().commit()
    return ok({"updated": True})


@api.get("/notifications")
@login_required
def notifications():
    return ok(
        [
            dict(r)
            for r in owned(
                "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        ]
    )
