"""User authentication — SQLite, bcrypt passwords, JWT tokens."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

_DB_DIR = Path(os.getenv("MITOFLOW_DATA_DIR", "./mitoflow_data"))
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "users.db"

# Simple JWT-like token using HMAC-SHA256 (no external deps)
_SECRET = os.getenv("MITOFLOW_SECRET", hashlib.sha256(os.urandom(32)).hexdigest())


def _get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(_DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db() -> None:
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT DEFAULT '',
            created_at REAL NOT NULL,
            last_login REAL NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    db.commit()
    db.close()


def _hash_password(password: str) -> str:
    """Hash password with salt using PBKDF2-SHA256."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    salt_hex, dk_hex = stored.split(":")
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return hmac.compare_digest(dk.hex(), dk_hex)


def _make_token(user_id: int) -> str:
    """Create a signed token."""
    payload = json.dumps({"uid": user_id, "iat": int(time.time()), "exp": int(time.time()) + 86400 * 30})
    sig = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + "." + sig


def _verify_token(token: str) -> Optional[int]:
    """Verify token and return user_id, or None."""
    try:
        payload, sig = token.rsplit(".", 1)
        expected = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(payload)
        if data["exp"] < time.time():
            return None
        return data["uid"]
    except Exception:
        return None


def register_user(email: str, username: str, password: str) -> Dict[str, Any]:
    """Register a new user. Returns user dict or error."""
    if len(password) < 6:
        return {"error": "Password must be at least 6 characters"}
    if "@" not in email or "." not in email:
        return {"error": "Invalid email address"}

    db = _get_db()
    try:
        ph = _hash_password(password)
        now = time.time()
        db.execute(
            "INSERT INTO users (email, username, password_hash, created_at, last_login) VALUES (?, ?, ?, ?, ?)",
            (email.strip().lower(), username.strip(), ph, now, now),
        )
        db.commit()
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return {"id": user_id, "email": email, "username": username}
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            return {"error": "Email already registered"}
        return {"error": "Username already taken"}
    finally:
        db.close()


def login_user(email: str, password: str) -> Dict[str, Any]:
    """Login user. Returns token + user dict, or error."""
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not row:
            return {"error": "Invalid email or password"}
        if not _verify_password(password, row["password_hash"]):
            return {"error": "Invalid email or password"}

        now = time.time()
        token = _make_token(row["id"])
        # Store session
        db.execute(
            "INSERT INTO sessions (user_id, token, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (row["id"], token, now, now + 86400 * 30),
        )
        # Update last login
        db.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
        db.commit()

        return {
            "token": token,
            "user": {
                "id": row["id"],
                "email": row["email"],
                "username": row["username"],
                "api_key": row["api_key"] or "",
            },
        }
    finally:
        db.close()


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Get user info from token."""
    user_id = _verify_token(token)
    if not user_id:
        return None
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return None
        return {"id": row["id"], "email": row["email"], "username": row["username"], "api_key": row["api_key"] or ""}
    finally:
        db.close()


def update_api_key(user_id: int, api_key: str) -> bool:
    """Update user's API key."""
    db = _get_db()
    try:
        db.execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, user_id))
        db.commit()
        return True
    finally:
        db.close()


# Initialize on import
init_db()
