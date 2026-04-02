import sqlite3
import hashlib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "finance.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            email     TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            role      TEXT NOT NULL CHECK(role IN ('admin','analyst','viewer')),
            status    TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','inactive')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS financial_records (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            amount     REAL NOT NULL,
            type       TEXT NOT NULL CHECK(type IN ('income','expense')),
            category   TEXT NOT NULL,
            date       TEXT NOT NULL,
            notes      TEXT,
            created_by INTEGER NOT NULL REFERENCES users(id),
            deleted_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()

    # Seed only if empty
    existing = cur.execute("SELECT id FROM users WHERE email='admin@finance.com'").fetchone()
    if existing:
        conn.close()
        return

    users = [
        ("Admin User",    "admin@finance.com",   hash_password("Admin@123"),   "admin"),
        ("Alice Analyst", "analyst@finance.com", hash_password("Analyst@123"), "analyst"),
        ("Victor Viewer", "viewer@finance.com",  hash_password("Viewer@123"),  "viewer"),
    ]
    cur.executemany(
        "INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)", users
    )
    conn.commit()

    admin_id = cur.execute(
        "SELECT id FROM users WHERE email='admin@finance.com'"
    ).fetchone()["id"]

    records = [
        (85000,  "income",  "Salary",    "2024-01-05", "Monthly salary",          admin_id),
        (1200,   "expense", "Rent",      "2024-01-10", "Office rent",             admin_id),
        (4500,   "expense", "Utilities", "2024-01-15", "Electricity and internet", admin_id),
        (32000,  "income",  "Freelance", "2024-02-01", "Consulting project",      admin_id),
        (8000,   "expense", "Software",  "2024-02-08", "SaaS subscriptions",      admin_id),
        (15000,  "income",  "Sales",     "2024-02-20", "Product sale Q1",         admin_id),
        (3200,   "expense", "Marketing", "2024-03-05", "Ad campaigns",            admin_id),
        (6700,   "expense", "Salary",    "2024-03-15", "Part-time staff",         admin_id),
        (22000,  "income",  "Salary",    "2024-03-01", "Monthly salary",          admin_id),
        (900,    "expense", "Travel",    "2024-03-22", "Client visit",            admin_id),
    ]
    cur.executemany(
        "INSERT INTO financial_records (amount, type, category, date, notes, created_by) "
        "VALUES (?,?,?,?,?,?)",
        records
    )
    conn.commit()
    conn.close()

    print("✅  Database seeded")
    print("    admin@finance.com   / Admin@123")
    print("    analyst@finance.com / Analyst@123")
    print("    viewer@finance.com  / Viewer@123")
