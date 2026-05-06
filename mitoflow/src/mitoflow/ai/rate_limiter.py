"""Rate limiting and resource control for multi-user MitoFlow.

Per-user and per-IP token bucket rate limiter, concurrency cap,
storage quota checks, and automatic old session cleanup.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class TokenBucket:
    """Token bucket rate limiter for a single user/IP."""
    rate: float          # tokens per second
    burst: int           # max burst size
    tokens: float = 0.0
    last_refill: float = 0.0

    def __post_init__(self):
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(float(self.burst), self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


@dataclass
class UserResource:
    """Track resource usage for a single user."""
    user_id: int
    concurrent_requests: int = 0
    total_requests: int = 0
    last_request_time: float = 0.0
    session_count: int = 0


class RateLimiter:
    """Multi-user rate limiter with per-user and per-IP tracking.

    Defaults:
    - AI chat: 10 req/min per user, burst 3
    - File upload: 5 req/min, burst 2
    - Auth endpoints: 20 req/min, burst 5
    - Max concurrent requests per user: 5
    - Max sessions per user: 50
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._buckets: Dict[str, TokenBucket] = {}
        self._users: Dict[int, UserResource] = {}

        # Config from environment
        self.chat_rate = float(os.getenv("MITOFLOW_CHAT_RATE", "10")) / 60  # per second
        self.chat_burst = int(os.getenv("MITOFLOW_CHAT_BURST", "3"))
        self.upload_rate = float(os.getenv("MITOFLOW_UPLOAD_RATE", "5")) / 60
        self.upload_burst = int(os.getenv("MITOFLOW_UPLOAD_BURST", "2"))
        self.max_concurrent = int(os.getenv("MITOFLOW_MAX_CONCURRENT", "5"))
        self.max_sessions = int(os.getenv("MITOFLOW_MAX_SESSIONS", "50"))

    def _get_bucket(self, key: str, rate: float, burst: int) -> TokenBucket:
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.rate != rate or bucket.burst != burst:
                bucket = TokenBucket(rate=rate, burst=burst)
                self._buckets[key] = bucket
            return bucket

    def check_chat(self, user_id: int, ip: str = "") -> bool:
        """Check if a chat request is allowed. Returns True if allowed."""
        user_key = f"chat:user:{user_id}"
        ip_key = f"chat:ip:{ip}" if ip else None

        with self._lock:
            user_res = self._users.get(user_id)
            if user_res is None:
                user_res = UserResource(user_id=user_id)
                self._users[user_id] = user_res

            if user_res.concurrent_requests >= self.max_concurrent:
                return False

        bucket = self._get_bucket(user_key, self.chat_rate, self.chat_burst)
        if not bucket.consume():
            return False

        if ip_key:
            ip_bucket = self._get_bucket(ip_key, self.chat_rate * 2, self.chat_burst)
            if not ip_bucket.consume():
                return False

        with self._lock:
            user_res = self._users[user_id]
            user_res.concurrent_requests += 1
            user_res.total_requests += 1
            user_res.last_request_time = time.time()

        return True

    def release_chat(self, user_id: int) -> None:
        with self._lock:
            user_res = self._users.get(user_id)
            if user_res and user_res.concurrent_requests > 0:
                user_res.concurrent_requests -= 1

    def check_upload(self, user_id: int, file_size: int = 0) -> bool:
        """Check if a file upload is allowed."""
        key = f"upload:user:{user_id}"
        bucket = self._get_bucket(key, self.upload_rate, self.upload_burst)
        return bucket.consume()

    def check_auth(self, ip: str = "") -> bool:
        """Check if an auth request is allowed. Per-IP bucket."""
        key = f"auth:ip:{ip}"
        # 20 req/min, burst 5
        bucket = self._get_bucket(key, 20.0 / 60, 5)
        return bucket.consume()

    def check_sessions(self, user_id: int) -> bool:
        """Check if a new session can be created."""
        with self._lock:
            user_res = self._users.get(user_id)
            if user_res is None:
                return True
            return user_res.session_count < self.max_sessions

    def add_session(self, user_id: int) -> None:
        with self._lock:
            user_res = self._users.get(user_id)
            if user_res is None:
                user_res = UserResource(user_id=user_id)
                self._users[user_id] = user_res
            user_res.session_count += 1

    def remove_session(self, user_id: int) -> None:
        with self._lock:
            user_res = self._users.get(user_id)
            if user_res and user_res.session_count > 0:
                user_res.session_count -= 1

    def get_user_stats(self, user_id: int) -> dict:
        with self._lock:
            user_res = self._users.get(user_id)
            if not user_res:
                return {"concurrent_requests": 0, "total_requests": 0}
            return {
                "concurrent_requests": user_res.concurrent_requests,
                "total_requests": user_res.total_requests,
                "session_count": user_res.session_count,
            }

    def cleanup_stale(self, max_age_seconds: int = 1800) -> int:
        """Remove stale bucket entries. Returns count removed."""
        with self._lock:
            stale = [
                k for k, b in self._buckets.items()
                if time.monotonic() - b.last_refill > max_age_seconds
            ]
            for k in stale:
                del self._buckets[k]
            return len(stale)


# ── Workspace cleanup ─────────────────────────────────────────────

def cleanup_old_sessions(
    workspace_root: Path | str,
    max_age_days: int = 30,
    dry_run: bool = False,
) -> list[str]:
    """Delete session directories older than max_age_days.

    Returns list of removed directory paths.
    """
    root = Path(workspace_root)
    if not root.exists():
        return []

    cutoff = time.time() - max_age_days * 86400
    removed = []

    for user_dir in root.iterdir():
        if not user_dir.is_dir() or not user_dir.name.startswith("user_"):
            continue
        sessions_dir = user_dir / "sessions"
        if not sessions_dir.exists():
            continue

        for session_dir in sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            try:
                mtime = session_dir.stat().st_mtime
                if mtime < cutoff:
                    if not dry_run:
                        shutil.rmtree(str(session_dir), ignore_errors=True)
                    removed.append(str(session_dir))
            except OSError:
                continue

    return removed


def get_user_disk_usage(user_root: Path) -> int:
    """Get total disk usage for a user in bytes."""
    total = 0
    if user_root.exists():
        for f in user_root.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    pass
    return total


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
