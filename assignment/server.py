#!/usr/bin/env python3
"""
Finance Dashboard API
Run: python3 server.py
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from database import init_db, get_db
from helpers  import send_json, Router
import handlers as h

# ── register routes ──────────────────────────────────────────────────────────

router = Router()

# Auth
router.post(r"/api/auth/login",  h.auth_login)
router.get( r"/api/auth/me",     h.auth_me)

# Users  (admin only)
router.get(   r"/api/users",               h.users_list)
router.get(   r"/api/users/(?P<user_id>\d+)", h.users_get)
router.post(  r"/api/users",               h.users_create)
router.put(   r"/api/users/(?P<user_id>\d+)", h.users_update)
router.delete(r"/api/users/(?P<user_id>\d+)", h.users_delete)

# Financial Records
router.get(   r"/api/records",                   h.records_list)
router.get(   r"/api/records/(?P<record_id>\d+)", h.records_get)
router.post(  r"/api/records",                   h.records_create)
router.put(   r"/api/records/(?P<record_id>\d+)", h.records_update)
router.delete(r"/api/records/(?P<record_id>\d+)", h.records_delete)

# Dashboard
router.get(r"/api/dashboard/summary",        h.dashboard_summary)
router.get(r"/api/dashboard/categories",     h.dashboard_categories)
router.get(r"/api/dashboard/trends/monthly", h.dashboard_monthly)
router.get(r"/api/dashboard/trends/weekly",  h.dashboard_weekly)
router.get(r"/api/dashboard/recent",         h.dashboard_recent)


# ── HTTP handler ─────────────────────────────────────────────────────────────

class FinanceHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _cors_preflight(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _health(self):
        from datetime import datetime
        send_json(self, 200, {"status": "ok", "timestamp": datetime.utcnow().isoformat()})

    def _dispatch(self, method):
        path = urlparse(self.path).path

        if path == "/api/health":
            return self._health()

        if not router.dispatch(self, method, self.path):
            send_json(self, 404, {"error": f"Route not found: {method} {path}"})

    def do_GET(self):    self._dispatch("GET")
    def do_POST(self):   self._dispatch("POST")
    def do_PUT(self):    self._dispatch("PUT")
    def do_DELETE(self): self._dispatch("DELETE")
    def do_OPTIONS(self):self._cors_preflight()


# ── start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    PORT = 3000
    server = HTTPServer(("0.0.0.0", PORT), FinanceHandler)
    print(f"\n🚀  Finance Dashboard API")
    print(f"    http://localhost:{PORT}/api/health\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
