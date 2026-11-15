"""
SDD Section 5.2.3: Auth Service
Implements REQ-AUTH-01, REQ-AUTH-02, REQ-AUTH-03, REQ-AUTH-04, NFR-SEC-03
- Supports University SSO/LDAP and fallback email/password login
- Salted PBKDF2-HMAC-SHA256 password hashing (zero plaintext passwords)
- Signed HMAC-SHA256 JWT tokens carrying user_id, email, full_name, and role
- Enforces 30-minute session inactivity timeout (REQ-AUTH-04)
- Enforces strict Role-Based Access Control (RBAC) for STUDENT, FACULTY, ADMIN
"""
import hashlib
import hmac
import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status, Header

from app.config import settings
from app.database import get_db_connection

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def parse_iso(ts_str: str) -> datetime:
    dt = datetime.strptime(ts_str[:19], "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)

def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"

def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3:
        return False
    _, salt, _ = parts
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, stored_hash)

def create_jwt_token(payload: Dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    s_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{h_b64}.{p_b64}.{s_b64}"

def decode_jwt_token(token: str) -> Dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token structure")
        h_b64, p_b64, s_b64 = parts
        signing_input = f"{h_b64}.{p_b64}".encode("utf-8")
        expected_sig = hmac.new(settings.JWT_SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(expected_b64, s_b64):
            raise ValueError("Invalid token signature")
        pad = "=" * (-len(p_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(p_b64 + pad).decode("utf-8"))
        return payload
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid session token: {exc}")

class AuthService:
    @staticmethod
    def authenticate_user(email: str, password: Optional[str] = None, is_sso: bool = False, db_path=None) -> Dict[str, Any]:
        conn = get_db_connection(db_path)
        try:
            row = conn.execute("SELECT * FROM Users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
            if not row:
                raise HTTPException(status_code=401, detail="Invalid university credentials or unknown account.")
            user = dict(row)
            if not user["is_active"]:
                raise HTTPException(status_code=403, detail="Account is deactivated. Contact Admin Staff.")

            if not is_sso:
                if not password or not verify_password(password, user["password_hash"] or ""):
                    raise HTTPException(status_code=401, detail="Invalid email or password.")

            now = datetime.now(timezone.utc)
            expires = now + timedelta(minutes=settings.SESSION_INACTIVITY_TIMEOUT_MIN)
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            exp_str = expires.strftime("%Y-%m-%d %H:%M:%S")

            cur = conn.execute(
                """
                INSERT INTO Sessions (user_id, title, started_at, last_activity_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (user["user_id"], "Academic & Campus Inquiry", now_str, now_str, exp_str),
            )
            session_id = cur.lastrowid
            conn.commit()

            token_payload = {
                "user_id": user["user_id"],
                "session_id": session_id,
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "department": user["department"],
                "iat": int(now.timestamp()),
            }
            jwt_token = create_jwt_token(token_payload)
            return {
                "token": jwt_token,
                "session_id": session_id,
                "user": {
                    "user_id": user["user_id"],
                    "email": user["email"],
                    "full_name": user["full_name"],
                    "role": user["role"],
                    "auth_source": user["auth_source"],
                    "department": user["department"],
                },
                "expires_at": exp_str,
            }
        finally:
            conn.close()

    @staticmethod
    def validate_session_and_role(
        token: str,
        allowed_roles: Optional[List[str]] = None,
        db_path=None
    ) -> Dict[str, Any]:
        payload = decode_jwt_token(token)
        session_id = payload.get("session_id")
        conn = get_db_connection(db_path)
        try:
            sess = conn.execute("SELECT * FROM Sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not sess:
                raise HTTPException(status_code=401, detail="Session not found. Please log in again.")
            sess_dict = dict(sess)
            if sess_dict["status"] != "ACTIVE":
                raise HTTPException(status_code=401, detail="Session has expired or ended. Please re-authenticate (REQ-AUTH-04).")

            now = datetime.now(timezone.utc)
            last_act = parse_iso(sess_dict["last_activity_at"])
            inactivity_minutes = (now - last_act).total_seconds() / 60.0

            # REQ-AUTH-04: Expire inactive session after 30 minutes
            if inactivity_minutes > settings.SESSION_INACTIVITY_TIMEOUT_MIN:
                conn.execute("UPDATE Sessions SET status = 'EXPIRED' WHERE session_id = ?", (session_id,))
                conn.commit()
                raise HTTPException(
                    status_code=401,
                    detail="Session expired after 30 minutes of inactivity (REQ-AUTH-04). Please log in again."
                )

            # Update last_activity_at and rolling expires_at
            new_now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            new_exp_str = (now + timedelta(minutes=settings.SESSION_INACTIVITY_TIMEOUT_MIN)).strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "UPDATE Sessions SET last_activity_at = ?, expires_at = ? WHERE session_id = ?",
                (new_now_str, new_exp_str, session_id)
            )
            conn.commit()

            # Check current user role from DB in case Admin updated it
            user_row = conn.execute("SELECT * FROM Users WHERE user_id = ?", (payload["user_id"],)).fetchone()
            if not user_row or not user_row["is_active"]:
                raise HTTPException(status_code=403, detail="User account is inactive.")
            current_role = user_row["role"]
            payload["role"] = current_role

            # REQ-AUTH-03 & NFR-SEC-03: Enforce RBAC
            if allowed_roles and current_role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied (REQ-AUTH-03): Role '{current_role}' is not authorized. Required: {', '.join(allowed_roles)}."
                )
            return payload
        finally:
            conn.close()
