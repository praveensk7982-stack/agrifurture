from functools import wraps
import re
import uuid
import time
import secrets
import datetime
from collections import defaultdict
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
from database import db
from routes.otp_routes import _send_mail, _hash_otp, EMAIL_RE, MAX_ATTEMPTS, RESEND_SECONDS, MAX_SENDS_PER_HOUR, _now

auth_bp = Blueprint("auth_bp", __name__)

# ===================================================================
# RATE LIMITING & SECURITY HELPERS
# ===================================================================
_login_failures = defaultdict(list)
_LOCKOUT_SECONDS = 300  # 5 minutes
_MAX_FAILURES = 5

def _is_rate_limited(email):
    now = time.time()
    attempts = [t for t in _login_failures[email] if now - t < _LOCKOUT_SECONDS]
    _login_failures[email] = attempts
    return len(attempts) >= _MAX_FAILURES

def _record_failure(email):
    now = time.time()
    _login_failures[email].append(now)

def _clear_failures(email):
    if email in _login_failures:
        del _login_failures[email]

def _safe(user):
    if not user:
        return None
    return {k: v for k, v in user.items() if k != "password_hash"}

def _validate_password(pwd):
    if not pwd or len(pwd) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", pwd) or not re.search(r"\d", pwd):
        return False, "Password must contain both letters and numbers."
    return True, ""

# ===================================================================
# RBAC MIDDLEWARE DECORATORS
# ===================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"error": "Authentication required. Please sign in."}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get("user_id"):
                return jsonify({"error": "Authentication required. Please sign in."}), 401
            user_role = session.get("role")
            if user_role not in allowed_roles:
                return jsonify({"error": "Forbidden: You do not have permission to access this resource."}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ===================================================================
# 3-STEP SIGNUP ENDPOINTS (Customer / Farmer / Machinery Seller)
# super_admin is strictly rejected with 403
# ===================================================================

@auth_bp.route("/api/auth/signup/send-otp", methods=["POST"])
def signup_send_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "")).strip().lower()

    # Reject super_admin self-registration
    if role == "super_admin":
        return jsonify({"error": "Admin accounts cannot be self-registered."}), 403

    if role not in ["customer", "farmer", "machinery_seller"]:
        return jsonify({"error": "Invalid role specified."}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    # Duplicate check: email already exists
    existing = db.get_user_by_email(email)
    if existing:
        return jsonify({"error": "An account with this email already exists. Please sign in."}), 409

    now = _now()
    conn = db._get_sqlite_conn()
    otp_role = f"signup_{role}"
    try:
        rows = conn.execute(
            "SELECT created_at FROM email_otps WHERE email = ? AND role = ? AND created_at > ? ORDER BY id DESC",
            (email, otp_role, (now - datetime.timedelta(hours=1)).isoformat()),
        ).fetchall()
        if rows:
            last = datetime.datetime.fromisoformat(rows[0]["created_at"])
            if (now - last).total_seconds() < RESEND_SECONDS:
                return jsonify({"error": f"Please wait {RESEND_SECONDS} seconds before requesting another OTP."}), 429
            if len(rows) >= MAX_SENDS_PER_HOUR:
                return jsonify({"error": "Too many OTP requests. Please try again in an hour."}), 429

        otp = f"{secrets.randbelow(10 ** 6):06d}"
        conn.execute("UPDATE email_otps SET used = 1 WHERE email = ? AND role = ? AND used = 0", (email, otp_role))
        cur = conn.execute(
            "INSERT INTO email_otps (email, role, otp_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
            (
                email,
                otp_role,
                _hash_otp(email, otp_role, otp),
                (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat(),
                now.isoformat(),
            ),
        )
        otp_id = cur.lastrowid
        conn.commit()

        try:
            _send_mail(email, otp)
        except Exception as e:
            print(f"[Signup OTP] Mail error: {e}")
            conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (otp_id,))
            conn.commit()
            return jsonify({"error": "Could not send verification email. Please try again."}), 500
    finally:
        conn.close()

    return jsonify({"message": f"Verification OTP sent to {email}."}), 200


@auth_bp.route("/api/auth/signup/verify-otp", methods=["POST"])
def signup_verify_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()

    if role == "super_admin":
        return jsonify({"error": "Admin accounts cannot be self-registered."}), 403

    if role not in ["customer", "farmer", "machinery_seller"] or not EMAIL_RE.match(email) or not re.fullmatch(r"\d{6}", otp):
        return jsonify({"error": "Valid email, role, and 6-digit OTP are required."}), 400

    otp_role = f"signup_{role}"
    now = _now()
    conn = db._get_sqlite_conn()
    import hmac
    try:
        rec = conn.execute(
            "SELECT * FROM email_otps WHERE email = ? AND role = ? AND used = 0 ORDER BY id DESC LIMIT 1",
            (email, otp_role),
        ).fetchone()
        if (
            not rec
            or datetime.datetime.fromisoformat(rec["expires_at"]) < now
            or rec["attempts"] >= MAX_ATTEMPTS
        ):
            return jsonify({"error": "OTP expired or invalid. Please request a new code."}), 400

        conn.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id = ?", (rec["id"],))
        if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, otp_role, otp)):
            conn.commit()
            left = MAX_ATTEMPTS - rec["attempts"] - 1
            return jsonify({"error": f"Wrong OTP. {left} attempt(s) left."}), 400

        # Mark OTP as successfully verified
        conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (rec["id"],))
        conn.commit()
    finally:
        conn.close()

    return jsonify({"message": "Email verified successfully!", "verified": True}), 200


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    full_name = str(data.get("full_name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    role = str(data.get("role", "customer")).strip().lower()
    location = str(data.get("location", "")).strip()
    otp = str(data.get("otp", "")).strip()

    # Reject self-registration for super_admin
    if role == "super_admin":
        return jsonify({"error": "Admin accounts cannot be self-registered."}), 403

    if role not in ["customer", "farmer", "machinery_seller"]:
        return jsonify({"error": "Invalid role specified."}), 400

    if not email or not password or not full_name:
        return jsonify({"error": "Full name, email, and password are required."}), 400

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please enter a valid email address."}), 400

    valid_pwd, pwd_err = _validate_password(password)
    if not valid_pwd:
        return jsonify({"error": pwd_err}), 400

    existing = db.get_user_by_email(email)
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 409

    # Verify that an OTP was verified or passed
    otp_role = f"signup_{role}"
    now = _now()
    conn = db._get_sqlite_conn()
    import hmac
    try:
        if otp and re.fullmatch(r"\d{6}", otp):
            # Check unused or recently verified OTP
            rec = conn.execute(
                "SELECT * FROM email_otps WHERE email = ? AND role = ? ORDER BY id DESC LIMIT 1",
                (email, otp_role),
            ).fetchone()
            if rec and rec["used"] == 0:
                if (datetime.datetime.fromisoformat(rec["expires_at"]) < now or
                        not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, otp_role, otp))):
                    return jsonify({"error": "Invalid or expired verification code."}), 400
                conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (rec["id"],))
                conn.commit()
    finally:
        conn.close()

    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": generate_password_hash(password),
        "full_name": full_name,
        "phone": phone,
        "role": role,
        "status": "active",
        "location": location or "India",
        "avatar_url": f"https://api.dicebear.com/7.x/bottts/svg?seed={email}",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    db.create_user(new_user)

    session.clear()
    session["user_id"] = new_user["id"]
    session["role"] = new_user["role"]
    session.permanent = True

    return jsonify({
        "message": f"Welcome to AGRO FUTURE, {full_name}!",
        "user": _safe(new_user)
    }), 201


# ===================================================================
# PUBLIC LOGIN (Customer / Farmer / Machinery Seller)
# Rejects wrong-role logins with generic error message
# ===================================================================
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "")).strip().lower()

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if _is_rate_limited(email):
        return jsonify({"error": "Too many failed login attempts. Please try again after 5 minutes."}), 429

    # If role is super_admin, route to 2-step admin login
    if role == "super_admin":
        return admin_verify_credentials()

    user = db.get_user_by_email(email)
    if not user:
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    if not check_password_hash(user.get("password_hash", ""), password):
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    # Role matching: strictly reject wrong-role login with generic error message
    if role and user.get("role") != role:
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    if user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended by the platform administrator."}), 403

    _clear_failures(email)
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session.permanent = True

    return jsonify({"message": "Login successful!", "user": _safe(user)}), 200


# ===================================================================
# ADMIN 2-STEP LOGIN (Credentials -> OTP -> Session)
# Only emails in ADMIN_EMAILS can access
# ===================================================================

@auth_bp.route("/api/auth/admin/verify-credentials", methods=["POST"])
def admin_verify_credentials():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if _is_rate_limited(email):
        return jsonify({"error": "Too many failed login attempts. Please try again after 5 minutes."}), 429

    # Whitelist check
    if email not in Config.ADMIN_EMAILS:
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    user = db.get_user_by_email(email)
    if not user or user.get("role") != "super_admin":
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    if not check_password_hash(user.get("password_hash", ""), password):
        _record_failure(email)
        return jsonify({"error": "Invalid email or password."}), 401

    if user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended."}), 403

    # Generate Admin OTP for Step 2 (Session NOT created yet!)
    now = _now()
    conn = db._get_sqlite_conn()
    try:
        otp = f"{secrets.randbelow(10 ** 6):06d}"
        conn.execute("UPDATE email_otps SET used = 1 WHERE email = ? AND role = 'super_admin' AND used = 0", (email,))
        cur = conn.execute(
            "INSERT INTO email_otps (email, role, otp_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
            (
                email,
                "super_admin",
                _hash_otp(email, "super_admin", otp),
                (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat(),
                now.isoformat(),
            ),
        )
        otp_id = cur.lastrowid
        conn.commit()

        try:
            _send_mail(email, otp)
        except Exception as e:
            print(f"[Admin OTP] Mail error: {e}")
            conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (otp_id,))
            conn.commit()
            return jsonify({"error": "Could not send authorization email. Please try again."}), 500
    finally:
        conn.close()

    return jsonify({
        "message": "Credentials verified. 6-digit authorization code sent to admin email.",
        "step": "otp_required",
        "email": email
    }), 200


@auth_bp.route("/api/auth/admin/verify-otp", methods=["POST"])
def admin_verify_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()

    if not email or not re.fullmatch(r"\d{6}", otp):
        return jsonify({"error": "Valid admin email and 6-digit OTP code are required."}), 400

    if _is_rate_limited(email):
        return jsonify({"error": "Too many failed attempts. Please try again after 5 minutes."}), 429

    if email not in Config.ADMIN_EMAILS:
        _record_failure(email)
        return jsonify({"error": "Invalid or expired authorization code."}), 401

    user = db.get_user_by_email(email)
    if not user or user.get("role") != "super_admin":
        _record_failure(email)
        return jsonify({"error": "Invalid or expired authorization code."}), 401

    now = _now()
    conn = db._get_sqlite_conn()
    import hmac
    try:
        rec = conn.execute(
            "SELECT * FROM email_otps WHERE email = ? AND role = 'super_admin' AND used = 0 ORDER BY id DESC LIMIT 1",
            (email,),
        ).fetchone()
        if (
            not rec
            or datetime.datetime.fromisoformat(rec["expires_at"]) < now
            or rec["attempts"] >= MAX_ATTEMPTS
        ):
            _record_failure(email)
            return jsonify({"error": "Invalid or expired authorization code."}), 401

        conn.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id = ?", (rec["id"],))
        if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, "super_admin", otp)):
            conn.commit()
            _record_failure(email)
            return jsonify({"error": "Invalid or expired authorization code."}), 401

        conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (rec["id"],))
        conn.commit()
    finally:
        conn.close()

    # Success: Create admin session
    _clear_failures(email)
    session.clear()
    session["user_id"] = user["id"]
    session["role"] = "super_admin"
    session.permanent = True

    return jsonify({"message": "Admin authorization successful!", "user": _safe(user)}), 200


# ===================================================================
# SESSION STATUS & LOGOUT
# ===================================================================
@auth_bp.route("/api/auth/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None, "authenticated": False}), 200

    user = db.get_user_by_id(user_id)
    if not user or user.get("status") == "suspended":
        session.clear()
        return jsonify({"user": None, "authenticated": False}), 200

    return jsonify({"user": _safe(user), "authenticated": True}), 200


@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."}), 200


# ===================================================================
# FORGOT PASSWORD (OTP-BASED, purpose="reset")
# Available for all roles
# ===================================================================
@auth_bp.route("/api/auth/forgot-password/send-otp", methods=["POST"])
def forgot_password_send_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    user = db.get_user_by_email(email)
    if not user:
        return jsonify({"error": "No account found with this email address."}), 404

    if user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended."}), 403

    now = _now()
    conn = db._get_sqlite_conn()
    try:
        rows = conn.execute(
            "SELECT created_at FROM email_otps WHERE email = ? AND role = 'reset' AND created_at > ? ORDER BY id DESC",
            (email, (now - datetime.timedelta(hours=1)).isoformat()),
        ).fetchall()
        if rows:
            last = datetime.datetime.fromisoformat(rows[0]["created_at"])
            if (now - last).total_seconds() < RESEND_SECONDS:
                return jsonify({"error": f"Please wait {RESEND_SECONDS} seconds before requesting another OTP."}), 429
            if len(rows) >= MAX_SENDS_PER_HOUR:
                return jsonify({"error": "Too many OTP requests. Please try again in an hour."}), 429

        otp = f"{secrets.randbelow(10 ** 6):06d}"
        conn.execute("UPDATE email_otps SET used = 1 WHERE email = ? AND role = 'reset' AND used = 0", (email,))
        cur = conn.execute(
            "INSERT INTO email_otps (email, role, otp_hash, expires_at, created_at) VALUES (?,?,?,?,?)",
            (
                email,
                "reset",
                _hash_otp(email, "reset", otp),
                (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat(),
                now.isoformat(),
            ),
        )
        otp_id = cur.lastrowid
        conn.commit()

        try:
            _send_mail(email, otp)
        except Exception as e:
            print(f"[Forgot Password] Mail error: {e}")
            conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (otp_id,))
            conn.commit()
            return jsonify({"error": "Could not send the OTP email. Please try again."}), 500
    finally:
        conn.close()

    return jsonify({"message": "Password reset OTP sent to your email."}), 200


@auth_bp.route("/api/auth/forgot-password/reset", methods=["POST"])
def forgot_password_reset():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()
    new_password = str(data.get("new_password", ""))

    if not EMAIL_RE.match(email) or not re.fullmatch(r"\d{6}", otp):
        return jsonify({"error": "Valid email and 6-digit OTP are required."}), 400

    valid_pwd, pwd_err = _validate_password(new_password)
    if not valid_pwd:
        return jsonify({"error": pwd_err}), 400

    user = db.get_user_by_email(email)
    if not user:
        return jsonify({"error": "No account found with this email."}), 404

    now = _now()
    conn = db._get_sqlite_conn()
    import hmac
    try:
        rec = conn.execute(
            "SELECT * FROM email_otps WHERE email = ? AND role = 'reset' AND used = 0 ORDER BY id DESC LIMIT 1",
            (email,),
        ).fetchone()
        if (
            not rec
            or datetime.datetime.fromisoformat(rec["expires_at"]) < now
            or rec["attempts"] >= MAX_ATTEMPTS
        ):
            return jsonify({"error": "OTP expired or invalid. Please request a new one."}), 400

        conn.execute("UPDATE email_otps SET attempts = attempts + 1 WHERE id = ?", (rec["id"],))
        if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, "reset", otp)):
            conn.commit()
            left = MAX_ATTEMPTS - rec["attempts"] - 1
            return jsonify({"error": f"Wrong OTP. {left} attempt(s) left."}), 400

        conn.execute("UPDATE email_otps SET used = 1 WHERE id = ?", (rec["id"],))
        conn.commit()
    finally:
        conn.close()

    # Update password
    new_hash = generate_password_hash(new_password)
    db.update_user_password(user["id"], new_hash)
    _clear_failures(email)

    return jsonify({"message": "Password reset successful! You can now sign in."}), 200
