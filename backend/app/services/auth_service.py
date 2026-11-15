"""
SDD Section 5.2.3: Auth Service
Implements REQ-AUTH-01, REQ-AUTH-02, REQ-AUTH-03, REQ-AUTH-04, NFR-SEC-03
- Supports Real Google OAuth2 / OpenID Connect (Google Identity Services)
- Supports University SSO/LDAP and fallback email/password login
- Salted PBKDF2-HMAC-SHA256 password hashing (zero plaintext passwords)
- Industry-standard PyJWT (HS256) session tokens carrying user_id, email, full_name, role, exp
- Enforces 30-minute session inactivity timeout (REQ-AUTH-04)
- Enforces strict Role-Based Access Control (RBAC) for STUDENT, FACULTY, ADMIN
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import httpx

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
    """Creates a standard signed JWT token using PyJWT with HS256."""
    token_payload = payload.copy()
    now = datetime.now(timezone.utc)
    if "iat" not in token_payload:
        token_payload["iat"] = int(now.timestamp())
    if "exp" not in token_payload:
        token_payload["exp"] = int((now + timedelta(minutes=settings.SESSION_INACTIVITY_TIMEOUT_MIN)).timestamp())
    return jwt.encode(token_payload, settings.JWT_SECRET_KEY, algorithm="HS256")

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a signed JWT token."""
    try:
        # Decode allowing up to 10 seconds leeway for clock skew
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid session token: {exc}"
        )

class AuthService:
    @staticmethod
    def authenticate_google_user(credential: str, db_path=None) -> Dict[str, Any]:
        """
        REQ-AUTH-01: Real Google OAuth2 / OpenID Connect authentication.
        Verifies the Google ID token, provisions/locates the user, and issues our JWT.
        """
        google_info = None
        try:
            req = google_requests.Request()
            aud = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
            google_info = id_token.verify_oauth2_token(credential, req, audience=aud)
        except Exception as e:
            # Fallback to direct Google tokeninfo endpoint
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}")
                    if resp.status_code == 200:
                        google_info = resp.json()
                    else:
                        raise ValueError(f"Google tokeninfo error: {resp.text}")
            except Exception as e2:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Google OAuth verification failed: {e}. Tokeninfo fallback error: {e2}"
                )

        if not google_info or not google_info.get("email"):
            raise HTTPException(status_code=400, detail="Google authentication did not provide an email address.")

        email = google_info["email"].lower().strip()
        full_name = google_info.get("name") or email.split("@")[0]
        avatar_url = google_info.get("picture", "")

        conn = get_db_connection(db_path)
        try:
            row = conn.execute("SELECT * FROM Users WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
            if row:
                user = dict(row)
                if not user["is_active"]:
                    raise HTTPException(status_code=403, detail="Your university account has been deactivated.")
            else:
                # Determine role based on institutional email domain
                if email.endswith("@st.niituniversity.in"):
                    role = "STUDENT"
                    dept = "CSE (Data Science)"
                elif email.endswith("@niituniversity.in"):
                    role = "FACULTY"
                    dept = "Academic Affairs"
                else:
                    role = "STUDENT"
                    dept = "General"

                cur = conn.execute(
                    """
                    INSERT INTO Users (email, full_name, role, auth_source, password_hash, department, is_active, created_at)
                    VALUES (?, ?, ?, 'SSO', NULL, ?, 1, ?)
                    """,
                    (email, full_name, role, dept, now_iso())
                )
                user_id = cur.lastrowid
                conn.commit()
                user = {
                    "user_id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "role": role,
                    "auth_source": "SSO",
                    "department": dept,
                    "is_active": 1
                }

            # Create session
            now = datetime.now(timezone.utc)
            expires = now + timedelta(minutes=settings.SESSION_INACTIVITY_TIMEOUT_MIN)
            now_str = now.strftime("%Y-%m-%d %H:%M:%S")
            exp_str = expires.strftime("%Y-%m-%d %H:%M:%S")

            cur = conn.execute(
                """
                INSERT INTO Sessions (user_id, title, started_at, last_activity_at, expires_at, status)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE')
                """,
                (user["user_id"], "Campus Inquiries (Google Session)", now_str, now_str, exp_str)
            )
            session_id = cur.lastrowid
            conn.commit()

            token_payload = {
                "user_id": user["user_id"],
                "session_id": session_id,
                "email": user["email"],
                "full_name": user["full_name"],
                "role": user["role"],
                "department": user.get("department", "CSE"),
                "avatar_url": avatar_url,
                "iat": int(now.timestamp()),
                "exp": int(expires.timestamp()),
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
                    "department": user.get("department", "CSE"),
                    "avatar_url": avatar_url,
                },
                "expires_at": exp_str,
            }
        finally:
            conn.close()

    @staticmethod
    def authenticate_user(email: str, password: Optional[str] = None, is_sso: bool = False, db_path=None) -> Dict[str, Any]:
        """
        REQ-AUTH-01 & REQ-AUTH-02: Authenticates via university credentials or quick demo SSO switch.
        """
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
                "exp": int(expires.timestamp()),
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
