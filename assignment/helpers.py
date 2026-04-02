import json
import re
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler
from auth import verify_token
from database import get_db


# ── tiny response helpers ────────────────────────────────────────────────────

def send_json(handler, status: int, data: dict):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
    handler.end_headers()
    handler.wfile.write(body)


def read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode()
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ── authentication / authorisation helpers ───────────────────────────────────

def get_current_user(handler):
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = verify_token(auth[7:])
    if not payload:
        return None
    db = get_db()
    user = db.execute(
        "SELECT id, name, email, role, status FROM users WHERE id=?",
        (payload["user_id"],)
    ).fetchone()
    db.close()
    if not user or user["status"] == "inactive":
        return None
    return dict(user)


def require_auth(handler):
    """Returns user dict or sends 401/403 and returns None."""
    user = get_current_user(handler)
    if not user:
        send_json(handler, 401, {"error": "Access denied. Please login."})
    return user


def require_role(handler, *roles):
    """Returns user dict if role matches, else sends error and returns None."""
    user = require_auth(handler)
    if not user:
        return None
    if user["role"] not in roles:
        send_json(handler, 403, {
            "error": f"Access denied. Required role: {' or '.join(roles)}.",
            "your_role": user["role"]
        })
        return None
    return user


# ── query string parser ───────────────────────────────────────────────────────

def parse_query(path: str) -> dict:
    qs = urlparse(path).query
    raw = parse_qs(qs)
    # flatten single-value lists
    return {k: v[0] if len(v) == 1 else v for k, v in raw.items()}


# ── simple pattern router ─────────────────────────────────────────────────────

class Router:
    def __init__(self):
        self._routes: list[tuple] = []   # (method, regex, handler_fn)

    def add(self, method: str, pattern: str, fn):
        self._routes.append((method.upper(), re.compile("^" + pattern + "$"), fn))

    def get(self, pattern, fn):   self.add("GET",    pattern, fn)
    def post(self, pattern, fn):  self.add("POST",   pattern, fn)
    def put(self, pattern, fn):   self.add("PUT",    pattern, fn)
    def delete(self, pattern, fn):self.add("DELETE", pattern, fn)

    def dispatch(self, handler: BaseHTTPRequestHandler, method: str, path: str):
        clean = urlparse(path).path
        for m, rx, fn in self._routes:
            if m == method:
                match = rx.match(clean)
                if match:
                    fn(handler, **match.groupdict())
                    return True
        return False
