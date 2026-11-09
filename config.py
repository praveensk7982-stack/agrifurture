import os
import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Environment detection
    IS_VERCEL = bool(os.getenv("VERCEL"))

    # Session signing key. Read from environment variable.
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        # Development / build fallback so import never crashes
        SECRET_KEY = "agro-future-dev-key-change-in-production"

    # Supabase Configuration (values come from .env / Vercel dashboard)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "dfxdclhujahjhxfsbepi")

    # Default Commission Rates
    DEFAULT_PRODUCE_COMMISSION = float(os.getenv("DEFAULT_PRODUCE_COMMISSION", "5.0"))
    DEFAULT_MACHINERY_COMMISSION = float(os.getenv("DEFAULT_MACHINERY_COMMISSION", "10.0"))

    # Database Mode: on Vercel, force 'supabase'; locally fall back according to DB_MODE
    DB_MODE = "supabase" if IS_VERCEL else os.getenv("DB_MODE", "auto")
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agro_future.db")

    # Email OTP login
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")
    ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()]
    OTP_TTL_MINUTES = 5

    # Session cookie safety: HttpOnly, Secure, SameSite=Lax for production
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_VERCEL or (os.getenv("COOKIE_SECURE") == "1") or (os.getenv("FLASK_DEBUG") != "1")