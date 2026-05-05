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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DB_DIR = Path(os.getenv("MITOFLOW_DATA_DIR", _PROJECT_ROOT / "mitoflow_data"))
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DB_PATH = _DB_DIR / "users.db"

# Simple JWT-like token using HMAC-SHA256 (no external deps)
_SECRET = os.getenv("MITOFLOW_SECRET")
if not _SECRET:
    import warnings
    warnings.warn(
        "MITOFLOW_SECRET is not set. JWT tokens will NOT survive server restarts. "
        "Set MITOFLOW_SECRET to a persistent 64-char hex string for production.",
        RuntimeWarning,
        stacklevel=2,
    )
    _SECRET = hashlib.sha256(os.urandom(32)).hexdigest()


def _get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(_DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def _add_column_if_missing(db: sqlite3.Connection, table: str, column: str, dtype: str) -> None:
    """Add a column if it doesn't already exist."""
    cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {dtype}")


def init_db() -> None:
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT DEFAULT '',
            institution TEXT DEFAULT '',
            role TEXT DEFAULT '',
            degree TEXT DEFAULT '',
            created_at REAL NOT NULL,
            last_login REAL NOT NULL
        )
    """)
    # Migrate existing tables: add new columns if missing
    _add_column_if_missing(db, "users", "institution", "TEXT DEFAULT ''")
    _add_column_if_missing(db, "users", "role", "TEXT DEFAULT ''")
    _add_column_if_missing(db, "users", "degree", "TEXT DEFAULT ''")
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
    """Hash password with salt using PBKDF2-SHA256 (600k iterations, OWASP 2023)."""
    salt = os.urandom(16)
    iterations = 600000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return salt.hex() + ":" + str(iterations) + ":" + dk.hex()


def _verify_password(password: str, stored: str) -> bool:
    """Verify password against stored hash. Supports legacy (salt:dk) and new (salt:iterations:dk) formats."""
    parts = stored.split(":")
    if len(parts) == 3:
        salt_hex, iterations_str, dk_hex = parts
        iterations = int(iterations_str)
    elif len(parts) == 2:
        salt_hex, dk_hex = parts
        iterations = 100000  # legacy fallback
    else:
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
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
                "institution": row["institution"] or "",
                "role": row["role"] or "",
                "degree": row["degree"] or "",
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
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "institution": row["institution"] or "",
            "role": row["role"] or "",
            "degree": row["degree"] or "",
            "api_key": row["api_key"] or "",
        }
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


def update_profile(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update user profile fields. Returns updated user dict or error."""
    allowed = {"username", "institution", "role", "degree"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return {"error": "No valid fields to update"}
    db = _get_db()
    try:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        db.commit()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "institution": row["institution"] or "",
            "role": row["role"] or "",
            "degree": row["degree"] or "",
            "api_key": row["api_key"] or "",
        }
    except sqlite3.IntegrityError:
        return {"error": "Username already taken"}
    finally:
        db.close()


def change_password(user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
    """Change user password after verifying old password."""
    if len(new_password) < 6:
        return {"error": "New password must be at least 6 characters"}
    db = _get_db()
    try:
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return {"error": "User not found"}
        if not _verify_password(old_password, row["password_hash"]):
            return {"error": "Current password is incorrect"}
        new_hash = _hash_password(new_password)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# Initialize on import
init_db()
