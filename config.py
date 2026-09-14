import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "agro-future-secret-key-2026-supersecure")
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dfxdclhujahjhxfsbepi.supabase.co")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRmeGRjbGh1amFoamh4ZnNiZXBpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkxMjU3NDUsImV4cCI6MjEwNDcwMTc0NX0.hN-7ErS5OPJgKSs6xK9iHmWcslS1btB1fE7GLpUuIIA")
    SUPABASE_PROJECT_ID = os.getenv("SUPABASE_PROJECT_ID", "dfxdclhujahjhxfsbepi")
    
    # Default Commission Rates
    DEFAULT_PRODUCE_COMMISSION = float(os.getenv("DEFAULT_PRODUCE_COMMISSION", "5.0"))
    DEFAULT_MACHINERY_COMMISSION = float(os.getenv("DEFAULT_MACHINERY_COMMISSION", "10.0"))
    
    # Database Mode: 'auto', 'supabase', or 'sqlite'
    DB_MODE = os.getenv("DB_MODE", "auto")
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agro_future.db")
