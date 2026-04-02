"""
All route handler functions.
Each function receives (handler, **path_params).
"""

import hashlib
import re
from datetime import datetime

from auth import create_token
from database import get_db, hash_password
from helpers import send_json, read_body, require_auth, require_role, parse_query


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════

def auth_login(handler):
    body = read_body(handler)
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return send_json(handler, 400, {"error": "Email and password are required."})

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()
    db.close()

    if not user or user["password"] != hash_password(password):
        return send_json(handler, 401, {"error": "Invalid email or password."})

    if user["status"] == "inactive":
        return send_json(handler, 403, {"error": "Account is inactive. Contact admin."})

    token = create_token({"user_id": user["id"], "role": user["role"]})
    send_json(handler, 200, {
        "message": "Login successful.",
        "token": token,
        "user": {
            "id": user["id"], "name": user["name"],
            "email": user["email"], "role": user["role"]
        }
    })


def auth_me(handler):
    user = require_auth(handler)
    if user:
        send_json(handler, 200, {"user": user})


# ═══════════════════════════════════════════════════════════════════════════════
# USERS  (admin only)
# ═══════════════════════════════════════════════════════════════════════════════

def users_list(handler):
    user = require_role(handler, "admin")
    if not user:
        return

    q = parse_query(handler.path)
    page  = max(1, int(q.get("page", 1)))
    limit = max(1, min(100, int(q.get("limit", 10))))
    offset = (page - 1) * limit

    where = "WHERE 1=1"
    params = []
    if q.get("role"):
        where += " AND role=?"; params.append(q["role"])
    if q.get("status"):
        where += " AND status=?"; params.append(q["status"])

    db = get_db()
    total = db.execute(f"SELECT COUNT(*) as c FROM users {where}", params).fetchone()["c"]
    rows  = db.execute(
        f"SELECT id,name,email,role,status,created_at FROM users {where} "
        f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    db.close()

    send_json(handler, 200, {
        "data": [dict(r) for r in rows],
        "pagination": {"total": total, "page": page, "limit": limit,
                       "pages": -(-total // limit)}
    })


def users_get(handler, user_id):
    actor = require_role(handler, "admin")
    if not actor:
        return
    db = get_db()
    row = db.execute(
        "SELECT id,name,email,role,status,created_at FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    db.close()
    if not row:
        return send_json(handler, 404, {"error": "User not found."})
    send_json(handler, 200, {"data": dict(row)})


def users_create(handler):
    actor = require_role(handler, "admin")
    if not actor:
        return

    body = read_body(handler)
    name     = (body.get("name") or "").strip()
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    role     = body.get("role") or ""

    errors = []
    if not name:                              errors.append({"field":"name","message":"Name is required."})
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email): errors.append({"field":"email","message":"Valid email required."})
    if len(password) < 6:                     errors.append({"field":"password","message":"Password must be ≥6 chars."})
    if role not in ("admin","analyst","viewer"): errors.append({"field":"role","message":"Role must be admin/analyst/viewer."})
    if errors:
        return send_json(handler, 400, {"error": "Validation failed.", "details": errors})

    db = get_db()
    exists = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if exists:
        db.close()
        return send_json(handler, 409, {"error": "Email already registered."})

    cur = db.execute(
        "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
        (name, email, hash_password(password), role)
    )
    db.commit()
    new_user = db.execute(
        "SELECT id,name,email,role,status,created_at FROM users WHERE id=?",
        (cur.lastrowid,)
    ).fetchone()
    db.close()
    send_json(handler, 201, {"message": "User created.", "data": dict(new_user)})


def users_update(handler, user_id):
    actor = require_role(handler, "admin")
    if not actor:
        return

    db = get_db()
    existing = db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not existing:
        db.close()
        return send_json(handler, 404, {"error": "User not found."})

    existing = dict(existing)
    body = read_body(handler)

    # Self-protection rules
    if actor["id"] == int(user_id):
        if body.get("role") and body["role"] != existing["role"]:
            db.close()
            return send_json(handler, 400, {"error": "You cannot change your own role."})
        if body.get("status") == "inactive":
            db.close()
            return send_json(handler, 400, {"error": "You cannot deactivate your own account."})

    name     = body.get("name",     existing["name"])
    email    = body.get("email",    existing["email"])
    role     = body.get("role",     existing["role"])
    status   = body.get("status",   existing["status"])
    password = body.get("password")

    if role not in ("admin","analyst","viewer"):
        db.close()
        return send_json(handler, 400, {"error": "Invalid role."})
    if status not in ("active","inactive"):
        db.close()
        return send_json(handler, 400, {"error": "Invalid status."})

    new_pw = hash_password(password) if password else existing["password"]

    db.execute(
        "UPDATE users SET name=?,email=?,role=?,status=?,password=?,updated_at=datetime('now') WHERE id=?",
        (name, email.lower().strip(), role, status, new_pw, user_id)
    )
    db.commit()
    updated = db.execute(
        "SELECT id,name,email,role,status,created_at FROM users WHERE id=?", (user_id,)
    ).fetchone()
    db.close()
    send_json(handler, 200, {"message": "User updated.", "data": dict(updated)})


def users_delete(handler, user_id):
    actor = require_role(handler, "admin")
    if not actor:
        return

    if actor["id"] == int(user_id):
        return send_json(handler, 400, {"error": "You cannot delete your own account."})

    db = get_db()
    row = db.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        db.close()
        return send_json(handler, 404, {"error": "User not found."})

    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    db.close()
    send_json(handler, 200, {"message": "User deleted."})


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCIAL RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

def records_list(handler):
    user = require_role(handler, "admin", "analyst", "viewer")
    if not user:
        return

    q      = parse_query(handler.path)
    page   = max(1, int(q.get("page", 1)))
    limit  = max(1, min(100, int(q.get("limit", 10))))
    offset = (page - 1) * limit

    SORT_FIELDS = {"date","amount","category","type","created_at"}
    sort_by    = q.get("sort_by", "date") if q.get("sort_by") in SORT_FIELDS else "date"
    sort_order = "ASC" if q.get("sort_order","desc").lower() == "asc" else "DESC"

    where  = "WHERE deleted_at IS NULL"
    params = []

    if q.get("type"):        where += " AND type=?";              params.append(q["type"])
    if q.get("category"):    where += " AND category=?";          params.append(q["category"])
    if q.get("start_date"):  where += " AND date>=?";             params.append(q["start_date"])
    if q.get("end_date"):    where += " AND date<=?";             params.append(q["end_date"])
    if q.get("min_amount"):  where += " AND amount>=?";           params.append(float(q["min_amount"]))
    if q.get("max_amount"):  where += " AND amount<=?";           params.append(float(q["max_amount"]))
    if q.get("search"):
        where += " AND (notes LIKE ? OR category LIKE ?)"; params += [f"%{q['search']}%"]*2

    db    = get_db()
    total = db.execute(
        f"SELECT COUNT(*) as c FROM financial_records {where}", params
    ).fetchone()["c"]
    rows  = db.execute(
        f"SELECT r.*,u.name as created_by_name "
        f"FROM financial_records r JOIN users u ON r.created_by=u.id "
        f"{where} ORDER BY r.{sort_by} {sort_order} LIMIT ? OFFSET ?",
        params + [limit, offset]
    ).fetchall()
    db.close()

    send_json(handler, 200, {
        "data": [dict(r) for r in rows],
        "pagination": {"total": total, "page": page, "limit": limit,
                       "pages": -(-total // limit)}
    })


def records_get(handler, record_id):
    user = require_role(handler, "admin", "analyst", "viewer")
    if not user:
        return
    db  = get_db()
    row = db.execute(
        "SELECT r.*,u.name as created_by_name "
        "FROM financial_records r JOIN users u ON r.created_by=u.id "
        "WHERE r.id=? AND r.deleted_at IS NULL",
        (record_id,)
    ).fetchone()
    db.close()
    if not row:
        return send_json(handler, 404, {"error": "Record not found."})
    send_json(handler, 200, {"data": dict(row)})


def records_create(handler):
    user = require_role(handler, "admin")
    if not user:
        return

    body     = read_body(handler)
    amount   = body.get("amount")
    rtype    = body.get("type")
    category = (body.get("category") or "").strip()
    date     = body.get("date")
    notes    = body.get("notes")

    errors = []
    try:
        amount = float(amount)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        errors.append({"field":"amount","message":"Amount must be a positive number."})
    if rtype not in ("income","expense"):
        errors.append({"field":"type","message":"Type must be income or expense."})
    if not category:
        errors.append({"field":"category","message":"Category is required."})
    if not date or not re.match(r"\d{4}-\d{2}-\d{2}", str(date)):
        errors.append({"field":"date","message":"Date must be YYYY-MM-DD format."})
    if errors:
        return send_json(handler, 400, {"error": "Validation failed.", "details": errors})

    db  = get_db()
    cur = db.execute(
        "INSERT INTO financial_records (amount,type,category,date,notes,created_by) VALUES (?,?,?,?,?,?)",
        (amount, rtype, category, date, notes, user["id"])
    )
    db.commit()
    row = db.execute("SELECT * FROM financial_records WHERE id=?", (cur.lastrowid,)).fetchone()
    db.close()
    send_json(handler, 201, {"message": "Record created.", "data": dict(row)})


def records_update(handler, record_id):
    user = require_role(handler, "admin")
    if not user:
        return

    db       = get_db()
    existing = db.execute(
        "SELECT * FROM financial_records WHERE id=? AND deleted_at IS NULL", (record_id,)
    ).fetchone()
    if not existing:
        db.close()
        return send_json(handler, 404, {"error": "Record not found."})

    existing = dict(existing)
    body     = read_body(handler)
    amount   = body.get("amount",   existing["amount"])
    rtype    = body.get("type",     existing["type"])
    category = body.get("category", existing["category"])
    date     = body.get("date",     existing["date"])
    notes    = body.get("notes",    existing["notes"])

    try:
        amount = float(amount)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        db.close()
        return send_json(handler, 400, {"error": "Amount must be a positive number."})
    if rtype not in ("income","expense"):
        db.close()
        return send_json(handler, 400, {"error": "Type must be income or expense."})

    db.execute(
        "UPDATE financial_records SET amount=?,type=?,category=?,date=?,notes=?,updated_at=datetime('now') WHERE id=?",
        (amount, rtype, category, date, notes, record_id)
    )
    db.commit()
    updated = db.execute("SELECT * FROM financial_records WHERE id=?", (record_id,)).fetchone()
    db.close()
    send_json(handler, 200, {"message": "Record updated.", "data": dict(updated)})


def records_delete(handler, record_id):
    user = require_role(handler, "admin")
    if not user:
        return

    db  = get_db()
    row = db.execute(
        "SELECT id FROM financial_records WHERE id=? AND deleted_at IS NULL", (record_id,)
    ).fetchone()
    if not row:
        db.close()
        return send_json(handler, 404, {"error": "Record not found."})

    db.execute(
        "UPDATE financial_records SET deleted_at=datetime('now') WHERE id=?", (record_id,)
    )
    db.commit()
    db.close()
    send_json(handler, 200, {"message": "Record deleted (soft delete)."})


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD  (analyst + admin)
# ═══════════════════════════════════════════════════════════════════════════════

def _date_filter(q):
    where, params = "WHERE deleted_at IS NULL", []
    if q.get("start_date"): where += " AND date>=?"; params.append(q["start_date"])
    if q.get("end_date"):   where += " AND date<=?"; params.append(q["end_date"])
    return where, params


def dashboard_summary(handler):
    user = require_role(handler, "admin", "analyst")
    if not user:
        return

    q = parse_query(handler.path)
    where, params = _date_filter(q)

    db  = get_db()
    row = db.execute(
        f"SELECT "
        f"  SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as total_income, "
        f"  SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as total_expenses, "
        f"  COUNT(*) as total_records "
        f"FROM financial_records {where}",
        params
    ).fetchone()
    db.close()

    income   = row["total_income"]   or 0
    expenses = row["total_expenses"] or 0
    send_json(handler, 200, {"data": {
        "total_income":   income,
        "total_expenses": expenses,
        "net_balance":    income - expenses,
        "total_records":  row["total_records"] or 0,
    }})


def dashboard_categories(handler):
    user = require_role(handler, "admin", "analyst")
    if not user:
        return

    q = parse_query(handler.path)
    where, params = _date_filter(q)
    if q.get("type"):
        where += " AND type=?"; params.append(q["type"])

    db   = get_db()
    rows = db.execute(
        f"SELECT category, type, SUM(amount) as total, COUNT(*) as count "
        f"FROM financial_records {where} "
        f"GROUP BY category,type ORDER BY total DESC",
        params
    ).fetchall()
    db.close()
    send_json(handler, 200, {"data": [dict(r) for r in rows]})


def dashboard_monthly(handler):
    user = require_role(handler, "admin", "analyst")
    if not user:
        return

    q = parse_query(handler.path)
    where, params = "WHERE deleted_at IS NULL", []
    if q.get("year"):
        where += " AND strftime('%Y',date)=?"; params.append(str(q["year"]))

    db   = get_db()
    rows = db.execute(
        f"SELECT strftime('%Y-%m',date) as month, "
        f"  SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as income, "
        f"  SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expenses, "
        f"  SUM(CASE WHEN type='income'  THEN amount ELSE -amount END) as net "
        f"FROM financial_records {where} "
        f"GROUP BY strftime('%Y-%m',date) ORDER BY month ASC",
        params
    ).fetchall()
    db.close()
    send_json(handler, 200, {"data": [dict(r) for r in rows]})


def dashboard_weekly(handler):
    user = require_role(handler, "admin", "analyst")
    if not user:
        return

    db   = get_db()
    rows = db.execute(
        "SELECT strftime('%Y-W%W',date) as week, "
        "  SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) as income, "
        "  SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) as expenses "
        "FROM financial_records WHERE deleted_at IS NULL "
        "GROUP BY strftime('%Y-W%W',date) ORDER BY week DESC LIMIT 12"
    ).fetchall()
    db.close()
    send_json(handler, 200, {"data": [dict(r) for r in rows]})


def dashboard_recent(handler):
    user = require_role(handler, "admin", "analyst")
    if not user:
        return

    q     = parse_query(handler.path)
    limit = min(int(q.get("limit", 5)), 50)

    db   = get_db()
    rows = db.execute(
        "SELECT r.id,r.amount,r.type,r.category,r.date,r.notes,u.name as created_by_name "
        "FROM financial_records r JOIN users u ON r.created_by=u.id "
        "WHERE r.deleted_at IS NULL ORDER BY r.created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    db.close()
    send_json(handler, 200, {"data": [dict(r) for r in rows]})
