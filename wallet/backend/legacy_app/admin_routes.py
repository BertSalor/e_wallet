"""Administrator-only API for the BlueWallet admin console.

This module is intentionally isolated from the regular user API. It adds
admin-only tables and endpoints without changing user-facing business logic.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import Blueprint, request, jsonify, session, g, send_file, abort
from werkzeug.security import generate_password_hash
from config import DB_PATH
from .db import connect

admin_api = Blueprint("admin_api", __name__)
BACKUP_DIR = Path(DB_PATH).resolve().parent / "backups"


def response(data=None, status=200, **extra):
    result = {"success": True, "data": data}
    result.update(extra)
    return jsonify(result), status


def error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def db():
    if "admin_db" not in g:
        g.admin_db = connect()
    return g.admin_db


@admin_api.teardown_request
def close_admin_db(exc=None):
    conn = g.pop("admin_db", None)
    if conn is not None:
        conn.close()


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        uid = session.get("user_id")
        if not uid:
            return error("Please log in to continue.", 401)
        user = db().execute("SELECT role,is_active FROM users WHERE id=?", (uid,)).fetchone()
        if not user or not user["is_active"]:
            session.clear()
            return error("This account is unavailable.", 403)
        if user["role"] != "admin":
            return error("Administrator access is required.", 403)
        return fn(*args, **kwargs)
    return wrapped


def ensure_admin_tables():
    conn = connect()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS admin_activity_logs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          admin_user_id INTEGER,
          action TEXT NOT NULL,
          details TEXT DEFAULT '',
          ip_address TEXT DEFAULT '',
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(admin_user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS admin_announcements (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          body TEXT NOT NULL,
          audience TEXT NOT NULL DEFAULT 'all',
          created_by INTEGER,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS admin_settings (
          setting_key TEXT PRIMARY KEY,
          setting_value TEXT NOT NULL
        );
        """)
        defaults = {
          "application_name": "BlueWallet",
          "currency": "PHP",
          "registration_enabled": "true",
          "maintenance_mode": "false",
          "announcement_banner": ""
        }
        for key, value in defaults.items():
            conn.execute("INSERT OR IGNORE INTO admin_settings(setting_key,setting_value) VALUES(?,?)", (key, value))
        conn.commit()
    finally:
        conn.close()


def audit(action, details=""):
    db().execute(
      "INSERT INTO admin_activity_logs(admin_user_id,action,details,ip_address) VALUES(?,?,?,?)",
      (session.get("user_id"), action, str(details)[:1000], request.headers.get("X-Forwarded-For", request.remote_addr or "")[:100])
    )
    db().commit()


def get_json():
    return request.get_json(silent=True) or {}


@admin_api.get("/overview")
@admin_required
def overview():
    conn = db()
    scalar = lambda sql: conn.execute(sql).fetchone()[0]
    users = scalar("SELECT COUNT(*) FROM users")
    active = scalar("SELECT COUNT(*) FROM users WHERE is_active=1")
    disabled = users - active
    transactions = scalar("SELECT COUNT(*) FROM transactions")
    income = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE kind='income'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE kind='expense'").fetchone()[0]
    accounts = scalar("SELECT COUNT(*) FROM accounts")
    volume = conn.execute("SELECT COALESCE(SUM(amount),0) FROM transactions").fetchone()[0]
    monthly = conn.execute("""SELECT substr(transaction_date,1,7) month,
      SUM(CASE WHEN kind='income' THEN amount ELSE 0 END) income,
      SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END) expenses
      FROM transactions WHERE transaction_date >= date('now','-5 months','start of month')
      GROUP BY substr(transaction_date,1,7) ORDER BY month""").fetchall()
    recent = conn.execute("""SELECT t.id,t.kind,t.amount,t.transaction_date,t.note,u.email,
      COALESCE(p.full_name,'') full_name FROM transactions t JOIN users u ON u.id=t.user_id
      LEFT JOIN user_profiles p ON p.user_id=u.id ORDER BY t.id DESC LIMIT 8""").fetchall()
    return response({"total_users":users,"active_users":active,"disabled_users":disabled,
      "total_accounts":accounts,"total_transactions":transactions,"total_income":round(income,2),
      "total_expenses":round(expenses,2),"transaction_volume":round(volume,2),
      "monthly":[dict(x) for x in monthly],"recent_transactions":[dict(x) for x in recent]})


@admin_api.get("/users")
@admin_required
def users():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "all")
    query = """SELECT u.id,u.email,u.role,u.is_active,u.created_at,COALESCE(p.full_name,'') full_name,
      (SELECT COUNT(*) FROM transactions t WHERE t.user_id=u.id) transaction_count,
      (SELECT COUNT(*) FROM accounts a WHERE a.user_id=u.id) account_count
      FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id WHERE 1=1"""
    args = []
    if search:
        query += " AND (u.email LIKE ? OR p.full_name LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])
    if status == "active": query += " AND u.is_active=1"
    elif status == "disabled": query += " AND u.is_active=0"
    query += " ORDER BY u.created_at DESC,u.id DESC LIMIT 500"
    return response([dict(r) for r in db().execute(query,args).fetchall()])


@admin_api.patch("/users/<int:uid>")
@admin_required
def edit_user(uid):
    p=get_json(); name=str(p.get("full_name","")).strip(); email=str(p.get("email","")).strip().lower()
    if not name or len(name)>100 or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$",email):
        return error("Enter a valid name and email address.")
    if uid == session.get("user_id") and not email:
        return error("Invalid administrator details.")
    try:
        cur=db().execute("UPDATE users SET email=? WHERE id=?",(email,uid))
        if not cur.rowcount: return error("User not found.",404)
        db().execute("UPDATE user_profiles SET full_name=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",(name,uid))
        audit("Updated user",f"User ID {uid}")
        return response({"updated":True})
    except sqlite3.IntegrityError:
        db().rollback(); return error("That email address is already in use.",409)


@admin_api.patch("/users/<int:uid>/status")
@admin_required
def user_status(uid):
    active=get_json().get("is_active")
    if active not in (True,False,0,1): return error("Provide a valid account status.")
    if uid == session.get("user_id") and not bool(active): return error("You cannot disable your own administrator account.")
    target=db().execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
    if not target: return error("User not found.",404)
    if target["role"] == "admin" and not bool(active):
        admins=db().execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
        if admins <= 1: return error("The last active administrator cannot be disabled.")
    db().execute("UPDATE users SET is_active=? WHERE id=?",(int(bool(active)),uid))
    audit("Changed user status",f"User ID {uid}; active={bool(active)}")
    return response({"updated":True,"is_active":int(bool(active))})


@admin_api.delete("/users/<int:uid>")
@admin_required
def delete_user(uid):
    if uid == session.get("user_id"): return error("You cannot delete your own administrator account.")
    target=db().execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
    if not target: return error("User not found.",404)
    if target["role"] == "admin":
        n=db().execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
        if n<=1: return error("The last active administrator cannot be deleted.")
    db().execute("DELETE FROM users WHERE id=?",(uid,))
    audit("Deleted user",f"User ID {uid}")
    return response({"deleted":True})


@admin_api.get("/accounts")
@admin_required
def accounts():
    rows=db().execute("""SELECT a.id,a.user_id,a.name,a.kind,a.opening_balance,a.created_at,u.email,
      COALESCE(p.full_name,'') full_name,
      a.opening_balance + COALESCE((SELECT SUM(CASE WHEN t.kind='income' THEN t.amount WHEN t.kind='expense' THEN -t.amount ELSE 0 END) FROM transactions t WHERE t.account_id=a.id),0) balance
      FROM accounts a JOIN users u ON u.id=a.user_id LEFT JOIN user_profiles p ON p.user_id=u.id
      ORDER BY a.created_at DESC LIMIT 1000""").fetchall()
    return response([dict(r) for r in rows])


@admin_api.get("/transactions")
@admin_required
def transactions():
    q=request.args.get("q","").strip(); kind=request.args.get("kind","all"); start=request.args.get("start",""); end=request.args.get("end","")
    sql="""SELECT t.id,t.user_id,t.kind,t.amount,t.note,t.transaction_date,t.created_at,u.email,
      COALESCE(p.full_name,'') full_name,COALESCE(c.name,'Uncategorized') category,COALESCE(a.name,'—') account
      FROM transactions t JOIN users u ON u.id=t.user_id LEFT JOIN user_profiles p ON p.user_id=u.id
      LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN accounts a ON a.id=t.account_id WHERE 1=1"""
    args=[]
    if q: sql+=" AND (u.email LIKE ? OR p.full_name LIKE ? OR t.note LIKE ?)"; args += [f"%{q}%"]*3
    if kind in ("income","expense","transfer"): sql+=" AND t.kind=?"; args.append(kind)
    if start: sql+=" AND t.transaction_date>=?"; args.append(start)
    if end: sql+=" AND t.transaction_date<=?"; args.append(end)
    sql+=" ORDER BY t.transaction_date DESC,t.id DESC LIMIT 2000"
    return response([dict(r) for r in db().execute(sql,args).fetchall()])


@admin_api.get("/categories")
@admin_required
def categories():
    rows=db().execute("""SELECT c.id,c.user_id,c.name,c.kind,c.icon,c.color,c.is_default,u.email,
      COALESCE(p.full_name,'') full_name,(SELECT COUNT(*) FROM transactions t WHERE t.category_id=c.id) usage_count
      FROM categories c JOIN users u ON u.id=c.user_id LEFT JOIN user_profiles p ON p.user_id=u.id
      ORDER BY c.name COLLATE NOCASE LIMIT 2000""").fetchall()
    return response([dict(r) for r in rows])


@admin_api.post("/categories")
@admin_required
def add_category():
    p=get_json(); uid=p.get("user_id"); name=str(p.get("name","")).strip(); kind=p.get("kind")
    if not name or len(name)>60 or kind not in ("income","expense") or not uid: return error("Provide a valid user, category name, and type.")
    try:
        cur=db().execute("INSERT INTO categories(user_id,name,kind,icon,color,is_default) VALUES(?,?,?,?,?,0)",
          (int(uid),name,kind,str(p.get("icon","tag"))[:40],str(p.get("color","#268bd2"))[:20]))
        audit("Created category",f"Category {name}; user ID {uid}")
        return response({"id":cur.lastrowid},201)
    except (ValueError,sqlite3.IntegrityError): db().rollback(); return error("Could not create category. Check the user and duplicate category name.",409)


@admin_api.patch("/categories/<int:cid>")
@admin_required
def update_category(cid):
    p=get_json(); name=str(p.get("name","")).strip(); kind=p.get("kind")
    if not name or len(name)>60 or kind not in ("income","expense"): return error("Provide a valid category name and type.")
    cur=db().execute("UPDATE categories SET name=?,kind=?,icon=?,color=? WHERE id=?",
      (name,kind,str(p.get("icon","tag"))[:40],str(p.get("color","#268bd2"))[:20],cid))
    if not cur.rowcount: return error("Category not found.",404)
    audit("Updated category",f"Category ID {cid}")
    return response({"updated":True})


@admin_api.delete("/categories/<int:cid>")
@admin_required
def remove_category(cid):
    row=db().execute("SELECT is_default FROM categories WHERE id=?",(cid,)).fetchone()
    if not row: return error("Category not found.",404)
    used=db().execute("SELECT COUNT(*) FROM transactions WHERE category_id=?",(cid,)).fetchone()[0]
    if used: return error("This category is used by transactions. Keep it to preserve transaction history.",409)
    db().execute("DELETE FROM categories WHERE id=?",(cid,)); audit("Deleted category",f"Category ID {cid}")
    return response({"deleted":True})


@admin_api.get("/reports/summary")
@admin_required
def report_summary():
    start=request.args.get("start") or "0001-01-01"; end=request.args.get("end") or "9999-12-31"
    rows=db().execute("""SELECT substr(transaction_date,1,7) month,
      SUM(CASE WHEN kind='income' THEN amount ELSE 0 END) income,
      SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END) expenses,COUNT(*) transaction_count
      FROM transactions WHERE transaction_date BETWEEN ? AND ? GROUP BY substr(transaction_date,1,7) ORDER BY month""",(start,end)).fetchall()
    totals=db().execute("""SELECT COUNT(*) count,COALESCE(SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),0) income,
      COALESCE(SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END),0) expenses FROM transactions WHERE transaction_date BETWEEN ? AND ?""",(start,end)).fetchone()
    return response({"totals":dict(totals),"monthly":[dict(r) for r in rows]})


@admin_api.get("/reports/transactions.csv")
@admin_required
def export_transactions():
    rows=db().execute("""SELECT t.id,u.email,t.kind,t.amount,t.transaction_date,t.note,COALESCE(c.name,'') category
      FROM transactions t JOIN users u ON u.id=t.user_id LEFT JOIN categories c ON c.id=t.category_id
      ORDER BY t.transaction_date DESC,t.id DESC""").fetchall()
    output=io.StringIO(); writer=csv.writer(output); writer.writerow(["ID","User Email","Type","Amount PHP","Date","Note","Category"])
    for r in rows: writer.writerow(list(r))
    mem=io.BytesIO(output.getvalue().encode("utf-8-sig")); mem.seek(0)
    audit("Exported transaction report",f"Rows: {len(rows)}")
    return send_file(mem,mimetype="text/csv",as_attachment=True,download_name="bluewallet-transactions.csv")


@admin_api.get("/announcements")
@admin_required
def announcements():
    rows=db().execute("""SELECT a.*,u.email created_by_email FROM admin_announcements a LEFT JOIN users u ON u.id=a.created_by ORDER BY a.id DESC""").fetchall()
    return response([dict(r) for r in rows])


@admin_api.post("/announcements")
@admin_required
def create_announcement():
    p=get_json(); title=str(p.get("title","")).strip(); body=str(p.get("body","")).strip(); audience=str(p.get("audience","all"))
    if not title or not body or len(title)>120 or len(body)>2000: return error("Enter a title and message (maximum 120 and 2000 characters).")
    if audience!="all" and not audience.isdigit(): return error("Audience must be all users or a user ID.")
    cur=db().execute("INSERT INTO admin_announcements(title,body,audience,created_by) VALUES(?,?,?,?)",(title,body,audience,session["user_id"]))
    if audience=="all":
        db().execute("INSERT INTO notifications(user_id,title,body) SELECT id,?,? FROM users WHERE role='user' AND is_active=1",(title,body))
    else:
        db().execute("INSERT INTO notifications(user_id,title,body) SELECT id,?,? FROM users WHERE id=? AND role='user'",(title,body,int(audience)))
    audit("Published announcement",f"Announcement ID {cur.lastrowid}; audience={audience}")
    return response({"id":cur.lastrowid},201)


@admin_api.delete("/announcements/<int:aid>")
@admin_required
def delete_announcement(aid):
    cur=db().execute("DELETE FROM admin_announcements WHERE id=?",(aid,))
    if not cur.rowcount: return error("Announcement not found.",404)
    audit("Deleted announcement",f"Announcement ID {aid}")
    return response({"deleted":True})


@admin_api.get("/activity-logs")
@admin_required
def activity_logs():
    rows=db().execute("""SELECT l.*,u.email admin_email FROM admin_activity_logs l LEFT JOIN users u ON u.id=l.admin_user_id
      ORDER BY l.id DESC LIMIT 1000""").fetchall()
    return response([dict(r) for r in rows])


@admin_api.get("/settings")
@admin_required
def get_settings():
    return response({r["setting_key"]:r["setting_value"] for r in db().execute("SELECT * FROM admin_settings").fetchall()})


@admin_api.put("/settings")
@admin_required
def put_settings():
    p=get_json(); allowed={"application_name","currency","registration_enabled","maintenance_mode","announcement_banner"}
    for key,value in p.items():
        if key not in allowed: continue
        val=str(value).strip()
        if len(val)>500: return error(f"{key} is too long.")
        db().execute("INSERT INTO admin_settings(setting_key,setting_value) VALUES(?,?) ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value",(key,val))
    audit("Updated system settings",", ".join(k for k in p if k in allowed))
    return response({"updated":True})


@admin_api.get("/security/admins")
@admin_required
def admin_accounts():
    rows=db().execute("""SELECT u.id,u.email,u.is_active,u.created_at,COALESCE(p.full_name,'') full_name
      FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id WHERE u.role='admin' ORDER BY u.id""").fetchall()
    return response([dict(r) for r in rows])


@admin_api.post("/security/admins")
@admin_required
def promote_admin():
    p=get_json(); email=str(p.get("email","")).strip().lower(); password=str(p.get("password",""))
    if len(password)<12: return error("Temporary password must be at least 12 characters.")
    user=db().execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
    if not user: return error("Create the user account first, then grant administrator access.",404)
    db().execute("UPDATE users SET role='admin',password_hash=? WHERE id=?",(generate_password_hash(password),user["id"]))
    audit("Granted administrator access",f"User ID {user['id']}")
    return response({"updated":True})


@admin_api.patch("/security/admins/<int:uid>/revoke")
@admin_required
def revoke_admin(uid):
    if uid==session.get("user_id"): return error("You cannot revoke your own administrator access.")
    count=db().execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
    target=db().execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone()
    if not target or target["role"]!="admin": return error("Administrator not found.",404)
    if count<=1: return error("The last active administrator cannot be removed.")
    db().execute("UPDATE users SET role='user' WHERE id=?",(uid,)); audit("Revoked administrator access",f"User ID {uid}")
    return response({"updated":True})


@admin_api.get("/backups")
@admin_required
def list_backups():
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    items=[{"name":p.name,"size":p.stat().st_size,"created_at":datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")} for p in sorted(BACKUP_DIR.glob("bluewallet-*.db"),key=lambda x:x.stat().st_mtime,reverse=True)]
    return response(items)


@admin_api.post("/backups")
@admin_required
def create_backup():
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    filename="bluewallet-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".db"
    destination=BACKUP_DIR/filename
    source=connect(); target=sqlite3.connect(destination)
    try: source.backup(target); target.commit()
    finally: source.close(); target.close()
    audit("Created database backup",filename)
    return response({"name":filename},201)


@admin_api.get("/backups/<path:filename>")
@admin_required
def download_backup(filename):
    if not re.fullmatch(r"bluewallet-[0-9]{8}-[0-9]{6}\.db",filename): abort(404)
    path=BACKUP_DIR/filename
    if not path.is_file(): abort(404)
    audit("Downloaded database backup",filename)
    return send_file(path,as_attachment=True,download_name=filename)


@admin_api.post("/backups/restore")
@admin_required
def restore_backup():
    name=str(get_json().get("name",""))
    if not re.fullmatch(r"bluewallet-[0-9]{8}-[0-9]{6}\.db",name): return error("Invalid backup name.")
    source_path=BACKUP_DIR/name
    if not source_path.is_file(): return error("Backup not found.",404)
    # Validate integrity before touching the live database.
    check=sqlite3.connect(f"file:{source_path}?mode=ro",uri=True)
    try:
        integrity=check.execute("PRAGMA integrity_check").fetchone()[0]
        tables={r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if integrity!="ok" or not {"users","transactions","accounts"}.issubset(tables): return error("Backup validation failed.")
        safety_name="bluewallet-before-restore-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".db"
        BACKUP_DIR.mkdir(parents=True,exist_ok=True)
        live=connect(); safety=sqlite3.connect(BACKUP_DIR/safety_name)
        try: live.backup(safety); safety.commit()
        finally: live.close(); safety.close()
        target=connect()
        try: check.backup(target); target.commit()
        finally: target.close()
    finally: check.close()
    audit("Restored database backup",name)
    return response({"restored":True,"safety_backup":safety_name})




@admin_api.get("/pdc/report")
@admin_required
def pdc_report():
    """Generate the same financial report sequentially or with process workers."""
    from datetime import date
    from pdc.report_processor import run_parallel, run_sequential
    start = request.args.get("start") or "0001-01-01"
    end = request.args.get("end") or "9999-12-31"
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
        if start > end:
            return error("Start date must not be after end date.")
        mode = request.args.get("mode", "parallel")
        if mode not in ("parallel", "sequential"):
            return error("Mode must be parallel or sequential.")
        result = (run_parallel if mode == "parallel" else run_sequential)(str(DB_PATH), start, end)
        audit("Generated PDC report", f"mode={mode}; start={start}; end={end}")
        return response(result)
    except Exception as exc:
        return error(f"PDC report processing failed: {str(exc)[:240]}", 500)


@admin_api.get("/pdc/benchmark")
@admin_required
def pdc_benchmark():
    """Run an apples-to-apples sequential/process-pool comparison."""
    from datetime import date
    from pdc.report_processor import benchmark
    start = request.args.get("start") or "0001-01-01"
    end = request.args.get("end") or "9999-12-31"
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
        if start > end:
            return error("Start date must not be after end date.")
        result = benchmark(str(DB_PATH), start, end)
        audit("Ran PDC benchmark", f"start={start}; end={end}; speedup={result['speedup']}")
        return response(result)
    except Exception as exc:
        return error(f"PDC benchmark failed: {str(exc)[:240]}", 500)
