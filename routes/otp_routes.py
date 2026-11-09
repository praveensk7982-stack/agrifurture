"""Email OTP login for all 4 AGRO FUTURE panels (customer, farmer, machinery_seller, super_admin)."""
import re
import hmac
import hashlib
import secrets
import smtplib
import uuid
import datetime
from email.message import EmailMessage

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import generate_password_hash

from config import Config
from database import db

otp_bp = Blueprint("otp_bp", __name__)

ROLE_LABELS = {
    "customer": "Customer",
    "farmer": "Farmer",
    "machinery_seller": "Machinery Provider",
    "super_admin": "Admin",
}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_ATTEMPTS = 5          # wrong tries per OTP
RESEND_SECONDS = 60       # wait between OTP emails
MAX_SENDS_PER_HOUR = 5    # per email address


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _hash_otp(email, role, otp):
    msg = f"{email}|{role}|{otp}".encode()
    return hmac.new(Config.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _send_mail(to_email, otp):
    if not (Config.MAIL_USERNAME and Config.MAIL_APP_PASSWORD):
        if current_app.debug:                      # local testing only
            print(f"[DEV ONLY] OTP for {to_email}: {otp}")
            return
        raise RuntimeError("Email service is not configured")

    msg = EmailMessage()
    msg["Subject"] = "AGRO FUTURE login OTP"
    msg["From"] = f"AGRO FUTURE <{Config.MAIL_USERNAME}>"
    msg["To"] = to_email
    msg.set_content(
        f"Your AGRO FUTURE login OTP is {otp}\n\n"
        f"It is valid for {Config.OTP_TTL_MINUTES} minutes. Do not share it with anyone."
    )
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(Config.MAIL_USERNAME, Config.MAIL_APP_PASSWORD)
        smtp.send_message(msg)


def _safe(user):
    return {k: v for k, v in user.items() if k != "password_hash"}


@otp_bp.route("/api/auth/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "")).strip()

    if role not in ROLE_LABELS or not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address."}), 400

    ok_reply = jsonify({"message": "OTP sent. Check your email."})

    user = db.get_user_by_email(email)
    if role == "super_admin":
        # Admin: only whitelisted emails. Same reply either way, so nobody can probe admin emails.
        if email not in Config.ADMIN_EMAILS or (user and user["role"] != "super_admin"):
            return ok_reply
    elif user and user["role"] != role:
        label = ROLE_LABELS.get(user["role"], user["role"])
        return jsonify({"error": f"This email is registered as {label}. Please use that panel."}), 409

    if user and user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended."}), 403

    now = _now()
    since_iso = (now - datetime.timedelta(hours=1)).isoformat()
    rows = db.otp_recent_requests(email, since_iso=since_iso)
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
    db.otp_invalidate_unused(email, role)
    expires_at = (now + datetime.timedelta(minutes=Config.OTP_TTL_MINUTES)).isoformat()
    new_row = db.otp_insert(
        email=email,
        role=role,
        otp_hash=_hash_otp(email, role, otp),
        expires_at=expires_at,
        created_at=now.isoformat(),
    )
    otp_id = new_row.get("id") if new_row else None

    try:
        _send_mail(email, otp)
    except Exception as e:
        print(f"[OTP] mail error: {e}")
        if otp_id:
            db.otp_mark_used(otp_id)
        return jsonify({"error": "Could not send the email. Please try again."}), 500

    return ok_reply


@otp_bp.route("/api/auth/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "")).strip()
    otp = str(data.get("otp", "")).strip()

    if role not in ROLE_LABELS or not EMAIL_RE.match(email) or not re.fullmatch(r"\d{6}", otp):
        return jsonify({"error": "Enter the 6-digit OTP."}), 400

    rec = db.otp_get_latest_valid(email, role)
    if not rec or rec.get("attempts", 0) >= MAX_ATTEMPTS:
        return jsonify({"error": "OTP expired or invalid. Please request a new one."}), 400

    new_attempts = db.otp_increment_attempts(rec["id"])
    if not hmac.compare_digest(rec["otp_hash"], _hash_otp(email, role, otp)):
        left = max(0, MAX_ATTEMPTS - new_attempts)
        return jsonify({"error": f"Wrong OTP. {left} attempt(s) left."}), 400

    db.otp_mark_used(rec["id"])

    # OTP is correct -> find or create the account
    user = db.get_user_by_email(email)
    if role == "super_admin" and email not in Config.ADMIN_EMAILS:
        return jsonify({"error": "Access denied."}), 403
    if user and user["role"] != role:
        label = ROLE_LABELS.get(user["role"], user["role"])
        return jsonify({"error": f"This email is registered as {label}. Please use that panel."}), 409
    if user and user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended."}), 403

    if not user:
        name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            # nobody knows this password: these accounts sign in with OTP only
            "password_hash": generate_password_hash(secrets.token_urlsafe(32)),
            "full_name": name,
            "phone": "",
            "role": role,
            "status": "active",
            "location": "India",
            "avatar_url": f"https://api.dicebear.com/7.x/bottts/svg?seed={email}",
            "created_at": now.isoformat(),
        }
        db.create_user(user)

    session.clear()
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    session.permanent = True
    return jsonify({"message": "Login successful!", "user": _safe(user)})