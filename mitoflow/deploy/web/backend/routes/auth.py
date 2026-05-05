"""Authentication and user management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ApiKeyUpdate(BaseModel):
    api_key: str


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    institution: Optional[str] = None
    role: Optional[str] = None
    degree: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TestConnectionRequest(BaseModel):
    provider: str
    base_url: str = ""
    api_key: str
    model: str = ""


class SendCodeRequest(BaseModel):
    email: str
    purpose: str = "register"


class VerifyCodeRequest(BaseModel):
    email: str
    code: str
    purpose: str = "register"


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


def _require_auth(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    from mitoflow.ai.auth import get_user_by_token
    user = get_user_by_token(authorization[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


@router.post("/api/auth/register")
async def auth_register(req: RegisterRequest):
    """Register a new user account."""
    from mitoflow.ai.auth import register_user
    from mitoflow.ai.email_verification import verify_code as check_verification

    code = getattr(req, "verification_code", None)
    if code:
        result = check_verification(req.email, code, "register")
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

    result = register_user(req.email, req.username, req.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    """Login and get a session token."""
    from mitoflow.ai.auth import login_user
    result = login_user(req.email, req.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@router.post("/api/auth/me")
async def auth_me(authorization: str = Header(None)):
    """Get current user info from token."""
    return _require_auth(authorization)


@router.post("/api/auth/api-key")
async def auth_update_api_key(req: ApiKeyUpdate, authorization: str = Header(None)):
    """Update user's default API key."""
    user = _require_auth(authorization)
    from mitoflow.ai.auth import update_api_key
    update_api_key(user["id"], req.api_key)
    return {"ok": True}


@router.post("/api/auth/test-connection")
async def auth_test_connection(req: TestConnectionRequest):
    """Test a model connection with a minimal request."""
    import time as _time
    result: dict = {"ok": False, "latency_ms": 0, "model": "", "error": ""}

    if not req.api_key:
        result["error"] = "API key is required"
        return result

    try:
        if req.provider == "anthropic":
            from mitoflow.ai.providers import AnthropicAdapter
            from mitoflow.ai.models import AIMessage, ProviderRequest
            adapter = AnthropicAdapter(
                api_key=req.api_key,
                model=req.model or "claude-haiku-4-5-20251001",
                base_url=req.base_url or None,
            )
            start = _time.monotonic()
            adapter.create(ProviderRequest(
                model=req.model or "claude-haiku-4-5-20251001",
                messages=[AIMessage(role="user", content="Hi")],
                max_tokens=5,
            ))
            result["latency_ms"] = round((_time.monotonic() - start) * 1000)
            result["model"] = req.model
            result["ok"] = True
        else:
            from mitoflow.ai.providers import OpenAIChatAdapter
            from mitoflow.ai.models import AIMessage, ProviderRequest
            adapter = OpenAIChatAdapter(
                api_key=req.api_key,
                model=req.model or "gpt-4o-mini",
                base_url=req.base_url or None,
            )
            start = _time.monotonic()
            adapter.create(ProviderRequest(
                model=req.model or "gpt-4o-mini",
                messages=[AIMessage(role="user", content="Hi")],
                max_tokens=5,
            ))
            result["latency_ms"] = round((_time.monotonic() - start) * 1000)
            result["model"] = req.model
            result["ok"] = True
    except Exception as e:
        result["error"] = str(e)[:200]

    return result


@router.post("/api/auth/send-code")
async def auth_send_code(req: SendCodeRequest):
    """Send a verification code to email."""
    from mitoflow.ai.email_verification import store_verification_code, send_verification_email
    if req.purpose not in ("register", "reset_password"):
        raise HTTPException(status_code=400, detail="Invalid purpose")

    if req.purpose == "reset_password":
        from mitoflow.ai.auth import _get_db as get_auth_db
        db = get_auth_db()
        row = db.execute("SELECT id FROM users WHERE email = ?", (req.email.strip().lower(),)).fetchone()
        db.close()
        if not row:
            return {"ok": True, "message": "If the email is registered, a code has been sent."}

    code = store_verification_code(req.email, req.purpose)
    result = send_verification_email(req.email, code, req.purpose)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "ok": True,
        "message": "Verification code sent. Valid for 5 minutes.",
        "dev_code": code if result.get("dev_mode") else None,
    }


@router.post("/api/auth/verify-code")
async def auth_verify_code(req: VerifyCodeRequest):
    """Verify a code."""
    from mitoflow.ai.email_verification import verify_code as check_code
    result = check_code(req.email, req.code, req.purpose)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@router.post("/api/auth/forgot-password")
async def auth_forgot_password(req: SendCodeRequest):
    """Send a password reset code to email."""
    req.purpose = "reset_password"
    return await auth_send_code(req)


@router.post("/api/auth/reset-password")
async def auth_reset_password(req: ResetPasswordRequest):
    """Reset password using a reset token or verification code."""
    from mitoflow.ai.email_verification import verify_reset_token, reset_password
    from mitoflow.ai.auth import get_user_by_token

    user_id = verify_reset_token(req.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = reset_password(user_id, req.new_password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@router.get("/api/auth/profile")
async def auth_get_profile(authorization: str = Header(None)):
    """Get current user profile."""
    return _require_auth(authorization)


@router.post("/api/auth/profile")
async def auth_update_profile(req: ProfileUpdate, authorization: str = Header(None)):
    """Update user profile."""
    user = _require_auth(authorization)
    from mitoflow.ai.auth import update_profile
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = update_profile(user["id"], data)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/api/auth/change-password")
async def auth_change_password(req: ChangePasswordRequest, authorization: str = Header(None)):
    """Change password after verifying current password."""
    user = _require_auth(authorization)
    from mitoflow.ai.auth import change_password
    result = change_password(user["id"], req.old_password, req.new_password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result
