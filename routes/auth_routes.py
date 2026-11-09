from functools import wraps
import re
import hmac
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
            user_id = session.get("user_id")
            if not user_id:
                return jsonify({"error": "Authentication required. Please sign in."}), 401

            active_role = session.get("active_role") or session.get("role")
            if not active_role or active_role not in allowed_roles:
                return jsonify({"error": "Forbidden: You do not have permission to access this resource."}), 403

            # Server-side verification against user_roles (never trust client)
            if active_role == "super_admin":
                user = db.get_user_by_id(user_id)
                admin_emails = [e.lower() for e in Config.ADMIN_EMAILS]
                if not user or user.get("role") != "super_admin" or user.get("email", "").lower() not in admin_emails:
                    return jsonify({"error": "Forbidden: Admin authorization required."}), 403
            else:
                if not db.user_has_role(user_id, active_role):
                    return jsonify({"error": f"Forbidden: You do not have active access to the {active_role} workspace."}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ===================================================================
# 3-STEP SIGNUP ENDPOINTS (Customer / Farmer / Machinery Seller)
# super_admin is strictly rejected with 403
# ===================================================================

@auth_bp.route("/api/auth/signup/send-otp", methods=["POST"])
def signup_send_otp():
    try:
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        role = str(data.get("role", "")).strip().lower()

        # Reject super_admin self-registration
        if role == "super_admin":
            return jsonify({"error": "Admin accounts cannot be self-registered."}), 403

        # Whitelisted admin emails cannot use public signup
        if email in [e.lower() for e in Config.ADMIN_EMAILS]:
            return jsonify({"error": "Admin accounts cannot use public registration."}), 403

        if role not in ["customer", "farmer", "machinery_seller"]:
            return jsonify({"error": "Invalid role specified."}), 400

        if not EMAIL_RE.match(email):
            return jsonify({"error": "Please enter a valid email address."}), 400

        # One account per email: if account already exists, tell them to sign in & add workspace
        existing = db.get_user_by_email(email)
        if existing:
            return jsonify({"error": f"You already have an account. Sign in, then add the {role} workspace."}), 409

        now = _now()
        otp_role = f"signup_{role}"
        since_iso = (now - datetime.timedelta(hours=1)).isoformat()
        rows = db.otp_recent_requests(email, otp_role, since_iso)
        if rows:
            created_str = str(rows[0]["created_at"]).replace("Z", "+00:00")
            try:
                last = datetime.datetime.fromisoformat(created_str)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                last = now
            if (now - last).total_seconds() < RESEND_SECONDS:
                return jsonify({"error": f"Please wait {RESEND_SECONDS} seconds before requesting another OTP."}), 429
            if len(rows) >= MAX_SENDS_PER_HOUR:
                return jsonify({"error": "Too many OTP requests. Please try again in an hour."}), 429

        otp = f"{secrets.randbelow(10 ** 6):06d}"
        db.otp_invalidate_unused(email, otp_role)
        otp_hash = _hash_otp(email, otp_role, otp)
        expires_at = (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat()
        new_row = db.otp_insert(email, otp_role, otp_hash, expires_at, now.isoformat())
        otp_id = new_row.get("id") if new_row else None

        try:
            _send_mail(email, otp)
        except Exception as e:
            print(f"[Signup OTP] Mail error: {e}")
            if otp_id:
                db.otp_mark_used(otp_id)
            return jsonify({"error": "Could not send verification email. Please try again."}), 500

        return jsonify({"message": f"Verification OTP sent to {email}."}), 200

    except Exception as exc:
        import traceback
        print(f"[Signup send-otp Error] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return jsonify({"error": "Failed to send verification code. Please try again."}), 500


@auth_bp.route("/api/auth/signup/verify-otp", methods=["POST"])
def signup_verify_otp():
    try:
        data = request.get_json() or {}
        email = str(data.get("email", "")).strip().lower()
        role = str(data.get("role", "")).strip().lower()
        otp = str(data.get("otp", "")).strip()

        if role == "super_admin":
            return jsonify({"error": "Admin accounts cannot be self-registered."}), 403

        if role not in ["customer", "farmer", "machinery_seller"] or not EMAIL_RE.match(email) or not re.fullmatch(r"\d{6}", otp):
            return jsonify({"error": "Valid email, role, and 6-digit OTP are required."}), 400

        otp_role = f"signup_{role}"
        rec = db.otp_get_latest_valid(email, otp_role)

        if not rec or rec.get("attempts", 0) >= MAX_ATTEMPTS:
            return jsonify({"error": "OTP expired or invalid. Please request a new code."}), 400

        new_attempts = db.otp_increment_attempts(rec["id"])
        if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, otp_role, otp)):
            left = max(0, MAX_ATTEMPTS - new_attempts)
            if left == 0:
                db.otp_mark_used(rec["id"])
            return jsonify({"error": f"Wrong OTP. {left} attempt(s) left."}), 400

        # Mark OTP as successfully verified!
        db.otp_mark_verified(rec["id"])
        return jsonify({"message": "Email verified successfully!", "verified": True}), 200

    except Exception as exc:
        import traceback
        print(f"[Signup verify-otp Error] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return jsonify({"error": "Verification failed. Please try again."}), 500


@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
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

    # Whitelisted admin emails cannot use public signup
    if email in [e.lower() for e in Config.ADMIN_EMAILS]:
        return jsonify({"error": "Admin accounts cannot use public registration."}), 403

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
        return jsonify({"error": f"You already have an account. Sign in, then add the {role} workspace."}), 409

    # Register must return 403 unless the email was OTP-verified
    otp_role = f"signup_{role}"
    verified_rec = db.otp_get_verified(email, otp_role)

    # Fallback if user passed otp directly in payload and was not verified yet
    if not verified_rec and otp and re.fullmatch(r"\d{6}", otp):
        latest = db.otp_get_latest_valid(email, otp_role)
        if latest and hmac.compare_digest(latest["otp_hash"], _hash_otp(email, otp_role, otp)):
            verified_rec = latest

    if not verified_rec:
        return jsonify({"error": "Email verification is required before creating an account."}), 403

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
    db.add_user_role(new_user["id"], role, status="active")

    # Mark OTP as used so it cannot be reused
    if verified_rec and verified_rec.get("id"):
        db.otp_mark_used(verified_rec["id"])

    session.clear()
    session["user_id"] = new_user["id"]
    session["active_role"] = role
    session["role"] = role
    session.permanent = True

    return jsonify({
        "message": f"Welcome to AGRO FUTURE, {full_name}!",
        "user": _safe(new_user),
        "roles": db.get_user_roles(new_user["id"]),
        "active_role": role
    }), 201


# ===================================================================
# PUBLIC LOGIN (Customer / Farmer / Machinery Seller)
# Multi-Role: checks email + password, verifies requested workspace role
# ===================================================================
@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
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

    if user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended by the platform administrator."}), 403

    _clear_failures(email)

    # Check requested workspace role
    try:
        if role:
            if not db.user_has_role(user["id"], role):
                user_roles = db.get_user_roles(user["id"])
                active_roles = [r["role"] for r in user_roles if r.get("status") == "active"]
                return jsonify({
                    "error": f"You don't have a {role} workspace yet. Sign in and add it.",
                    "code": "role_missing",
                    "roles": active_roles,
                    "requested_role": role
                }), 403
            active_role = role
        else:
            user_roles = db.get_user_roles(user["id"])
            active_roles = [r["role"] for r in user_roles if r.get("status") == "active"]
            active_role = user.get("role") if user.get("role") in active_roles else (active_roles[0] if active_roles else "customer")

        session.clear()
        session["user_id"] = user["id"]
        session["active_role"] = active_role
        session["role"] = active_role
        session.permanent = True

        return jsonify({
            "message": "Login successful!",
            "user": _safe(user),
            "roles": db.get_user_roles(user["id"]),
            "active_role": active_role
        }), 200
    except Exception as exc:
        print(f"[AUTH LOGIN ROLE ERROR] {type(exc).__name__}: {str(exc)}")
        return jsonify({"error": f"Failed to verify workspace roles: {type(exc).__name__} - {str(exc)}"}), 500


# ===================================================================
# MULTI-ROLE WORKSPACE MANAGEMENT (Add Role & Switch Role)
# ===================================================================
@auth_bp.route("/api/auth/roles/add", methods=["POST"])
@login_required
def add_workspace_role():
    user_id = session.get("user_id")
    user = db.get_user_by_id(user_id)
    if not user or user.get("status") == "suspended":
        return jsonify({"error": "Account not found or suspended."}), 403

    # super_admin accounts cannot add marketplace roles
    if user.get("role") == "super_admin" or session.get("active_role") == "super_admin":
        return jsonify({"error": "Admin accounts cannot add marketplace roles."}), 403

    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "")).strip().lower()
    password = str(data.get("password", ""))

    if not role or not password:
        return jsonify({"error": "Role and password confirmation are required."}), 400

    # role must be customer, farmer or machinery_seller; NEVER super_admin
    if role == "super_admin" or role not in ["customer", "farmer", "machinery_seller"]:
        return jsonify({"error": "Invalid workspace role specified."}), 403

    # Re-check the password
    if not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Incorrect password."}), 401

    try:
        # If the role already exists (and is active), return 200 with current roles
        if db.user_has_role(user_id, role):
            session["active_role"] = role
            session["role"] = role
            return jsonify({
                "message": f"You already have the {role} workspace.",
                "roles": db.get_user_roles(user_id),
                "active_role": role
            }), 200

        # Farmer and machinery_seller roles are added as "active" for now
        # TODO: Admin approval can be added here for farmer/machinery_seller if needed in the future.
        db.add_user_role(user_id, role, status="active")
        session["active_role"] = role
        session["role"] = role

        return jsonify({
            "message": f"{role.replace('_', ' ').title()} workspace added successfully.",
            "roles": db.get_user_roles(user_id),
            "active_role": role
        }), 200
    except Exception as exc:
        print(f"[AUTH ADD ROLE ERROR] {type(exc).__name__}: {str(exc)}")
        return jsonify({"error": f"Failed to add workspace role: {type(exc).__name__} - {str(exc)}"}), 500


@auth_bp.route("/api/auth/switch-role", methods=["POST"])
@login_required
def switch_workspace_role():
    user_id = session.get("user_id")
    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "")).strip().lower()

    if not role:
        return jsonify({"error": "Role is required."}), 400

    try:
        # Verify that the user has that role active in user_roles
        if not db.user_has_role(user_id, role):
            return jsonify({"error": f"You do not have access to the {role} workspace."}), 403

        session["active_role"] = role
        session["role"] = role

        return jsonify({
            "message": f"Switched to {role.replace('_', ' ').title()} workspace.",
            "active_role": role,
            "roles": db.get_user_roles(user_id)
        }), 200
    except Exception as exc:
        print(f"[AUTH SWITCH ROLE ERROR] {type(exc).__name__}: {str(exc)}")
        return jsonify({"error": f"Failed to switch workspace role: {type(exc).__name__} - {str(exc)}"}), 500


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
    otp = f"{secrets.randbelow(10 ** 6):06d}"
    db.otp_invalidate_unused(email, "super_admin")
    expires_at = (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat()
    new_row = db.otp_insert(
        email=email,
        role="super_admin",
        otp_hash=_hash_otp(email, "super_admin", otp),
        expires_at=expires_at,
        created_at=now.isoformat(),
    )
    otp_id = new_row.get("id") if new_row else None

    try:
        _send_mail(email, otp)
    except Exception as e:
        print(f"[Admin OTP] Mail error: {e}")
        if otp_id:
            db.otp_mark_used(otp_id)
        return jsonify({"error": "Could not send authorization email. Please try again."}), 500

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

    rec = db.otp_get_latest_valid(email, "super_admin")
    if not rec or rec.get("attempts", 0) >= MAX_ATTEMPTS:
        _record_failure(email)
        return jsonify({"error": "Invalid or expired authorization code."}), 401

    db.otp_increment_attempts(rec["id"])
    if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, "super_admin", otp)):
        _record_failure(email)
        return jsonify({"error": "Invalid or expired authorization code."}), 401

    db.otp_mark_used(rec["id"])

    # Success: Create admin session
    _clear_failures(email)
    session.clear()
    session["user_id"] = user["id"]
    session["active_role"] = "super_admin"
    session["role"] = "super_admin"
    session.permanent = True

    return jsonify({
        "message": "Admin authorization successful!",
        "user": _safe(user),
        "roles": [{"role": "super_admin", "status": "active"}],
        "active_role": "super_admin"
    }), 200


# ===================================================================
# SESSION STATUS & LOGOUT
# ===================================================================
@auth_bp.route("/api/auth/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"user": None, "authenticated": False, "roles": [], "active_role": None}), 200

    user = db.get_user_by_id(user_id)
    if not user or user.get("status") == "suspended":
        session.clear()
        return jsonify({"user": None, "authenticated": False, "roles": [], "active_role": None}), 200

    roles = db.get_user_roles(user_id)
    active_role = session.get("active_role") or session.get("role") or user.get("role")

    # If active_role is not active in user_roles, select first active role
    if active_role != "super_admin" and not db.user_has_role(user_id, active_role):
        active_roles = [r["role"] for r in roles if r.get("status") == "active"]
        if active_roles:
            active_role = active_roles[0]
            session["active_role"] = active_role
            session["role"] = active_role

    return jsonify({
        "user": _safe(user),
        "authenticated": True,
        "roles": roles,
        "active_role": active_role
    }), 200


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
    since_iso = (now - datetime.timedelta(hours=1)).isoformat()
    rows = db.otp_recent_requests(email, "reset", since_iso)
    if rows:
        created_str = str(rows[0]["created_at"]).replace("Z", "+00:00")
        try:
            last = datetime.datetime.fromisoformat(created_str)
            if last.tzinfo is None:
                last = last.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            last = now
        if (now - last).total_seconds() < RESEND_SECONDS:
            return jsonify({"error": f"Please wait {RESEND_SECONDS} seconds before requesting another OTP."}), 429
        if len(rows) >= MAX_SENDS_PER_HOUR:
            return jsonify({"error": "Too many OTP requests. Please try again in an hour."}), 429

    otp = f"{secrets.randbelow(10 ** 6):06d}"
    db.otp_invalidate_unused(email, "reset")
    expires_at = (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat()
    new_row = db.otp_insert(
        email=email,
        role="reset",
        otp_hash=_hash_otp(email, "reset", otp),
        expires_at=expires_at,
        created_at=now.isoformat(),
    )
    otp_id = new_row.get("id") if new_row else None

    try:
        _send_mail(email, otp)
    except Exception as e:
        print(f"[Forgot Password] Mail error: {e}")
        if otp_id:
            db.otp_mark_used(otp_id)
        return jsonify({"error": "Could not send the OTP email. Please try again."}), 500

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

    rec = db.otp_get_latest_valid(email, "reset")
    if not rec or rec.get("attempts", 0) >= MAX_ATTEMPTS:
        return jsonify({"error": "OTP expired or invalid. Please request a new one."}), 400

    new_attempts = db.otp_increment_attempts(rec["id"])
    if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, "reset", otp)):
        left = max(0, MAX_ATTEMPTS - new_attempts)
        return jsonify({"error": f"Wrong OTP. {left} attempt(s) left."}), 400

    db.otp_mark_used(rec["id"])

    # Update password
    new_hash = generate_password_hash(new_password)
    db.update_user_password(user["id"], new_hash)
    _clear_failures(email)

    return jsonify({"message": "Password reset successful! You can now sign in."}), 200
