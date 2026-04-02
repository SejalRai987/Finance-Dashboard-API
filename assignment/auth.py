import base64
import hashlib
import hmac
import json
import time

SECRET = "finance_dashboard_secret_key_2024"
TOKEN_TTL = 86400  # 24 hours


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)


def create_token(payload: dict) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = {**payload, "exp": int(time.time()) + TOKEN_TTL, "iat": int(time.time())}
    body = _b64(json.dumps(payload).encode())
    sig = _b64(
        hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"


def verify_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected = _b64(
            hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
