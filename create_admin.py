#!/usr/bin/env python3
"""
CLI Script: create_admin.py
Sets up or updates a Super Admin account for AGRO FUTURE.
Security:
- Never hardcodes credentials. Prompts for email and password at runtime.
- Email must match one of the whitelisted emails in ADMIN_EMAILS (.env).
- Passwords are securely hashed with generate_password_hash (werkzeug).
- Writes to Supabase when configured, or local SQLite with user confirmation.
"""

import sys
import os
import re
import uuid
import getpass
import datetime
from dotenv import load_dotenv

# Ensure project root is in sys.path and load .env
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

from config import Config
from database import db
from werkzeug.security import generate_password_hash

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def validate_password(password):
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return False, "Password must contain both letters and numbers."
    return True, ""


def main():
    # 1. Target Database Selection & Confirmation
    if db.use_supabase:
        db_name = "Supabase (Live PostgreSQL)"
        print(f"Target Database: {db_name}")
    else:
        db_name = f"Local SQLite ({os.path.basename(Config.SQLITE_PATH)})"
        print("Supabase credentials not configured or inactive.")
        print(f"Target Database: {db_name}")
        try:
            confirm_sqlite = input("Use local SQLite database? (y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)
        if confirm_sqlite != "y":
            print("Aborted.")
            sys.exit(0)

    try:
        confirm = input(f"Writing to {db_name}. Continue? (y/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        sys.exit(0)

    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # 2. Prompt for admin email and password (asked twice)
    try:
        email = input("Enter admin email: ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        sys.exit(0)

    # 3. Validation
    if not email or not EMAIL_RE.match(email):
        print(f"Error: '{email}' is not a valid email address.")
        sys.exit(1)

    allowed_admin_emails = [e.lower() for e in Config.ADMIN_EMAILS if e.strip()]
    if not allowed_admin_emails:
        print("Error: No ADMIN_EMAILS configured in environment. Please set ADMIN_EMAILS in .env first.")
        sys.exit(1)

    if email not in allowed_admin_emails:
        print(f"Error: '{email}' is not authorized. Only emails listed in ADMIN_EMAILS are allowed.")
        sys.exit(1)

    try:
        password = input("Enter admin password: ");
        confirm_pwd = input("Confirm admin password: ")
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        sys.exit(0)

    if password != confirm_pwd:
        print("Error: Passwords do not match.")
        sys.exit(1)

    is_valid, msg = validate_password(password)
    if not is_valid:
        print(f"Error: {msg}")
        sys.exit(1)

    if len(password) < 12:
        print("Warning: Password is shorter than 12 characters (recommended: 12+ characters).")

    # 4. Hash password with werkzeug generate_password_hash
    password_hash = generate_password_hash(password)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Check if a profile with that email exists
    existing = db.get_user_by_email(email)
    if existing:
        try:
            update_confirm = input(f"Profile for '{email}' already exists. Update password and role to super_admin? (y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

        if update_confirm != "y":
            print("Aborted.")
            sys.exit(0)

        user_id = existing["id"]
        if db.use_supabase:
            try:
                db.client.table("profiles").update({
                    "password_hash": password_hash,
                    "role": "super_admin",
                    "status": "active"
                }).eq("id", user_id).execute()
            except Exception as e:
                print(f"[Supabase Admin Update Error] {e}")
                sys.exit(1)
        else:
            conn = db._get_sqlite_conn()
            try:
                conn.execute(
                    "UPDATE profiles SET password_hash = ?, role = 'super_admin', status = 'active' WHERE id = ?",
                    (password_hash, user_id)
                )
                conn.commit()
            finally:
                conn.close()
    else:
        user_id = str(uuid.uuid4())
        new_profile = {
            "id": user_id,
            "email": email,
            "password_hash": password_hash,
            "full_name": "Administrator",
            "phone": "",
            "role": "super_admin",
            "status": "active",
            "location": "Headquarters",
            "avatar_url": f"https://api.dicebear.com/7.x/bottts/svg?seed={email}",
            "created_at": now_iso
        }
        db.create_user(new_profile)

    # 5. Make sure active row exists in user_roles (db helper never sends "id" to Supabase)
    db.add_user_role(user_id, "super_admin", status="active")

    # 6. Print only "Admin account ready for <email>" at the end
    print(f"Admin account ready for {email}")


if __name__ == "__main__":
    main()
