import os
import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Session signing key. NO default: the app must not start without it.
    SECRET_KEY = os.environ["SECRET_KEY"]

    # Supabase Configuration (values come from .env / hosting dashboard)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "dfxdclhujahjhxfsbepi")

    # Default Commission Rates
    DEFAULT_PRODUCE_COMMISSION = float(os.getenv("DEFAULT_PRODUCE_COMMISSION", "5.0"))
    DEFAULT_MACHINERY_COMMISSION = float(os.getenv("DEFAULT_MACHINERY_COMMISSION", "10.0"))

    # Database Mode: 'auto', 'supabase', or 'sqlite'
    DB_MODE = os.getenv("DB_MODE", "auto")
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agro_future.db")

    # Email OTP login
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_APP_PASSWORD = os.getenv("MAIL_APP_PASSWORD")
    ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "admin@agrofuture.com").split(",") if e.strip()]
    OTP_TTL_MINUTES = 5

    # Session cookie safety
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE") == "1"   # set 1 only on a real HTTPS server