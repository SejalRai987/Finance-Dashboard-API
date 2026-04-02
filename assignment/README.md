# Finance Dashboard API

A backend REST API for a finance dashboard system with role-based access control,
financial record management, and analytics. Built with **pure Python 3** — zero
external dependencies.

---

# Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Built-in `http.server` + `sqlite3` — no installs needed |
| Database | SQLite (built-in) | Zero setup, file-based|
| Auth | HMAC-SHA256 tokens | JWT-style tokens using only `hashlib` + `hmac` |
| Password hashing | SHA-256 (built-in `hashlib`) | No bcrypt dependency |
| Server | `http.server.HTTPServer` | Python standard library |

---

# Project structure

```
finance-api/
├── server.py       # Entry point — starts HTTPServer, registers all routes
├── handlers.py     # All route handler functions (auth, users, records, dashboard)
├── helpers.py      # Request/response helpers, Router class, auth middleware
├── auth.py         # HMAC-SHA256 token creation and verification
├── database.py     # SQLite schema, connection, seed data
├── finance.db      # Auto-created on first run
└── README.md
```

---

## Setup & Run

```bash
# No installation needed — pure Python 3
python3 server.py
```

Server starts at `http://localhost:3000`

### Default Credentials (seeded automatically)

| Email | Password | Role |
|---|---|---|
| admin@finance.com | Admin@123 | admin |
| analyst@finance.com | Analyst@123 | analyst |
| viewer@finance.com | Viewer@123 | viewer |

---

## Role Permissions

| Action | viewer | analyst | admin |
|---|:---:|:---:|:---:|
| Login | ✅ | ✅ | ✅ |
| View financial records | ✅ | ✅ | ✅ |
| Filter / search records | ✅ | ✅ | ✅ |
| Create / update / delete records | ❌ | ❌ | ✅ |
| View dashboard summary & analytics | ❌ | ✅ | ✅ |
| View / manage users | ❌ | ❌ | ✅ |

---

## API Reference

### Authentication

All protected endpoints require the header:
```
Authorization: Bearer <token>
```

#### `POST /api/auth/login`
```json
{ "email": "admin@finance.com", "password": "Admin@123" }
```
Response:
```json
{
  "message": "Login successful.",
  "token": "<jwt-style token>",
  "user": { "id": 1, "name": "Admin User", "email": "...", "role": "admin" }
}
```

#### `GET /api/auth/me`
Returns the currently authenticated user. Requires any valid token.

---

### Financial Records

#### `GET /api/records`
List records with optional filters. Accessible by all roles.

| Query param | Example | Description |
|---|---|---|
| `type` | `income` or `expense` | Filter by type |
| `category` | `Salary` | Filter by category |
| `start_date` | `2024-01-01` | Date range start (inclusive) |
| `end_date` | `2024-03-31` | Date range end (inclusive) |
| `min_amount` | `1000` | Minimum amount |
| `max_amount` | `50000` | Maximum amount |
| `search` | `salary` | Search notes and category |
| `sort_by` | `amount` | Sort field (date/amount/category/type) |
| `sort_order` | `asc` | Sort direction (asc/desc) |
| `page` | `1` | Page number |
| `limit` | `10` | Items per page |

#### `GET /api/records/:id`
Get a single record by ID. All roles.

#### `POST /api/records`
Create a new record. **Admin only.**
```json
{
  "amount": 5000,
  "type": "income",
  "category": "Salary",
  "date": "2024-04-01",
  "notes": "Optional description"
}
```

#### `PUT /api/records/:id`
Update a record. **Admin only.**

#### `DELETE /api/records/:id`
Soft-delete a record (sets `deleted_at`). **Admin only.**

---

### Dashboard Analytics

All dashboard endpoints require **analyst or admin** role.

#### `GET /api/dashboard/summary`
Returns total income, expenses, net balance, and record count.
Supports `?start_date=` and `?end_date=` filters.
```json
{
  "data": {
    "total_income": 154000.0,
    "total_expenses": 24500.0,
    "net_balance": 129500.0,
    "total_records": 10
  }
}
```

#### `GET /api/dashboard/categories`
Category-wise breakdown of income and expenses.
Supports `?type=income|expense`, `?start_date=`, `?end_date=`.

#### `GET /api/dashboard/trends/monthly`
Month-by-month income, expenses, and net. Supports `?year=2024`.

#### `GET /api/dashboard/trends/weekly`
Weekly income vs expenses (last 12 weeks).

#### `GET /api/dashboard/recent`
Most recent records. Supports `?limit=5` (max 50).

---

### User Management

All user endpoints require **admin** role.

#### `GET /api/users`
List all users. Supports `?role=`, `?status=`, `?page=`, `?limit=`.

#### `GET /api/users/:id`
Get a user by ID.

#### `POST /api/users`
Create a new user.
```json
{
  "name": "New User",
  "email": "new@example.com",
  "password": "Secret@123",
  "role": "viewer"
}
```

#### `PUT /api/users/:id`
Update user fields (name, email, password, role, status).
Self-protection: admins cannot change their own role or deactivate themselves.

#### `DELETE /api/users/:id`
Hard-delete a user. Admins cannot delete themselves.

---

### Health Check

#### `GET /api/health`
```json
{ "status": "ok", "timestamp": "2024-04-01T10:00:00" }
```

---

## Validation Rules

| Field | Rule |
|---|---|
| `email` | Must match `x@x.x` format |
| `password` | Minimum 6 characters |
| `role` | Must be `admin`, `analyst`, or `viewer` |
| `amount` | Must be a positive number (> 0) |
| `type` | Must be `income` or `expense` |
| `date` | Must match `YYYY-MM-DD` format |
| `category` | Required, non-empty string |

---

## Error Response Format

All errors return a consistent JSON shape:

```json
{ "error": "Description of what went wrong." }
```

Validation errors include field-level detail:
```json
{
  "error": "Validation failed.",
  "details": [
    { "field": "amount", "message": "Amount must be a positive number." }
  ]
}
```

### HTTP Status Codes Used

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing/invalid/expired token) |
| 403 | Forbidden (insufficient role) |
| 404 | Not Found |
| 409 | Conflict (e.g. duplicate email) |
| 500 | Internal Server Error |

---

## Design Decisions & Assumptions

### Soft Delete
Financial records use soft delete (`deleted_at` timestamp). Deleted records
are invisible to all API queries but remain in the database for audit purposes.
Users are hard-deleted since they don't represent immutable financial history.

### Password Hashing
Uses SHA-256 via Python's built-in `hashlib`. In production, use `bcrypt` or
`argon2` with a proper salt. This choice was made to eliminate all external
dependencies.

### Token Authentication
Implements a JWT-compatible HMAC-SHA256 token scheme using only Python builtins
(`hmac`, `hashlib`, `base64`). Tokens expire after 24 hours. In production,
use the `PyJWT` library.

### Role Hierarchy
Three roles with clear separation:
- **viewer** — read-only access to records
- **analyst** — read records + full dashboard analytics
- **admin** — full system access (records CRUD + user management)

### No External Dependencies
The entire project runs with `python3 server.py` and nothing else. This was a
deliberate choice to make the project instantly runnable on any machine with
Python 3.6+.

### SQLite WAL Mode
WAL (Write-Ahead Logging) mode is enabled for better concurrent read performance,
even though this is a single-user dev setup.

---
# Running it

```bash
python3 - <<'EOF'
# Paste the test script from the project, or run inline:
import threading
from http.server import HTTPServer
from database import init_db
from server import FinanceHandler

init_db()
httpd = HTTPServer(("127.0.0.1", 3001), FinanceHandler)
# ... see test suite
EOF
```

The test suite covers 48 cases: auth, record CRUD, role enforcement,
input validation, pagination, filtering, dashboard analytics, and edge cases.
