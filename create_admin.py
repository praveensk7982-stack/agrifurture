#!/usr/bin/env python3
"""
CLI Script: create_admin.py
Sets up or updates a Super Admin account for AGRO FUTURE.
Security:
- Email must match one of the whitelisted emails in ADMIN_EMAILS (.env).
- Passwords are securely hashed with scrypt (generate_password_hash).
- Supports interactive input (with masked password via getpass) and CLI args.
"""

import sys
import os
import re
import uuid
import getpass
import argparse
import datetime

# Ensure project root is in sys.path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

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
    parser = argparse.ArgumentParser(description="Create or update an AGRO FUTURE Super Admin account.")
    parser.add_argument("--email", help="Super Admin email address (must be in ADMIN_EMAILS whitelist)")
    parser.add_argument("--password", help="Super Admin password (min 8 chars, letters + numbers)")
    parser.add_argument("--name", default="Super Admin", help="Full name of administrator")
    parser.add_argument("--phone", default="", help="Optional contact phone")
    args = parser.parse_args()

    allowed_admin_emails = [e.lower() for e in Config.ADMIN_EMAILS]
    if not allowed_admin_emails:
        print("[ERROR] No ADMIN_EMAILS configured in .env. Please set ADMIN_EMAILS first.")
        sys.exit(1)

    print("==================================================")
    print("      AGRO FUTURE - Super Admin CLI Setup         ")
    print("==================================================")
    print(f"Whitelisted Admin Emails (.env): {', '.join(allowed_admin_emails)}\n")

    # 1. Obtain email
    email = args.email
    if not email:
        try:
            email = input("Enter admin email address: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)
    else:
        email = email.strip().lower()

    if not EMAIL_RE.match(email):
        print(f"[ERROR] '{email}' is not a valid email address.")
        sys.exit(1)

    if email not in allowed_admin_emails:
        print(f"[ERROR] '{email}' is NOT in the ADMIN_EMAILS whitelist.")
        print(f"Allowed emails: {', '.join(allowed_admin_emails)}")
        sys.exit(1)

    # 2. Obtain password
    password = args.password
    if not password:
        try:
            password = getpass.getpass("Enter admin password: ")
            confirm = getpass.getpass("Confirm admin password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

        if password != confirm:
            print("[ERROR] Passwords do not match.")
            sys.exit(1)

    is_valid, msg = validate_password(password)
    if not is_valid:
        print(f"[ERROR] {msg}")
        sys.exit(1)

    # 3. Hash password
    password_hash = generate_password_hash(password)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 4. Check if profile exists
    existing = db.get_user_by_email(email)
    if existing:
        print(f"Updating existing account '{email}' to Super Admin...")
        conn = db._get_sqlite_conn()
        try:
            conn.execute(
                "UPDATE profiles SET password_hash = ?, role = 'super_admin', status = 'active' WHERE email = ?",
                (password_hash, email)
            )
            conn.commit()
        finally:
            conn.close()
        print(f"[OK] Successfully updated Super Admin account for {email}!")
    else:
        print(f"Creating new Super Admin profile for '{email}'...")
        user_id = str(uuid.uuid4())
        full_name = args.name or "Super Admin"
        new_profile = {
            "id": user_id,
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
            "phone": args.phone or "",
            "role": "super_admin",
            "status": "active",
            "location": "Headquarters",
            "avatar_url": f"https://api.dicebear.com/7.x/bottts/svg?seed={email}",
            "created_at": now
        }
        db.create_user(new_profile)
        print(f"[OK] Successfully created Super Admin account for {email} (ID: {user_id})!")

    print("\nAdministrator is ready to log in via the 2-step verification flow.")
    print("==================================================")


if __name__ == "__main__":
    main()
