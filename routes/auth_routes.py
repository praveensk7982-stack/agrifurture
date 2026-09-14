from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import datetime
from database import db

auth_bp = Blueprint("auth_bp", __name__)

DEMO_USERS = {
    "super_admin": "admin@agrofuture.com",
    "farmer": "farmer.rajesh@agrofuture.com",
    "machinery_seller": "seller.kumar@agrofuture.com",
    "customer": "customer.anita@agrofuture.com"
}

@auth_bp.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    role = data.get("role", "customer").strip().lower()
    location = data.get("location", "").strip()

    if not email or not password or not full_name:
        return jsonify({"error": "Email, password, and full name are required."}), 400

    if role not in ["customer", "farmer", "machinery_seller"]:
        return jsonify({"error": "Invalid role specified."}), 400

    existing = db.get_user_by_email(email)
    if existing:
        return jsonify({"error": "An account with this email already exists."}), 409

    # Generate avatar url
    avatar_url = f"https://api.dicebear.com/7.x/bottts/svg?seed={email}"

    new_user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": generate_password_hash(password),
        "full_name": full_name,
        "phone": phone,
        "role": role,
        "status": "active",
        "location": location or "India",
        "avatar_url": avatar_url,
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    db.create_user(new_user)
    
    # Store in session
    session["user_id"] = new_user["id"]
    session["role"] = new_user["role"]

    safe_user = {k: v for k, v in new_user.items() if k != "password_hash"}
    return jsonify({"message": "Registration successful!", "user": safe_user}), 201

@auth_bp.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = db.get_user_by_email(email)
    if not user:
        return jsonify({"error": "Invalid email or password."}), 401

    # Check demo hash or hashed password
    pwd_hash = user.get("password_hash", "")
    password_ok = False
    if "$demo" in pwd_hash:
        # Permissive for preset demo accounts or standard check
        password_ok = True
    else:
        password_ok = check_password_hash(pwd_hash, password)

    if not password_ok:
        return jsonify({"error": "Invalid email or password."}), 401

    if user.get("status") == "suspended":
        return jsonify({"error": "This account has been suspended by the platform administrator."}), 403

    session["user_id"] = user["id"]
    session["role"] = user["role"]

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return jsonify({"message": "Login successful!", "user": safe_user}), 200

@auth_bp.route("/api/auth/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        # Default fallback to customer for seamless preview
        user = db.get_user_by_email(DEMO_USERS["customer"])
        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            safe_user = {k: v for k, v in user.items() if k != "password_hash"}
            return jsonify({"user": safe_user, "authenticated": True})
        return jsonify({"user": None, "authenticated": False})

    user = db.get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"user": None, "authenticated": False})

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return jsonify({"user": safe_user, "authenticated": True})

@auth_bp.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully."})

@auth_bp.route("/api/auth/switch-demo-role", methods=["POST"])
def switch_demo_role():
    """Allows rapid switching between all 4 roles for instant evaluation."""
    data = request.get_json() or {}
    target_role = data.get("role", "customer").strip().lower()

    if target_role not in DEMO_USERS:
        return jsonify({"error": "Invalid demo role."}), 400

    target_email = DEMO_USERS[target_role]
    user = db.get_user_by_email(target_email)
    if not user:
        return jsonify({"error": "Demo user not found."}), 404

    session["user_id"] = user["id"]
    session["role"] = user["role"]

    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return jsonify({
        "message": f"Switched perspective to {user['full_name']} ({user['role']})",
        "user": safe_user
    })
