import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

    JWT_SECRET = os.environ.get("JWT_SECRET")
    JWT_EXPIRY_DAYS = int(os.environ.get("JWT_EXPIRY_DAYS", 30))

    PORT = int(os.environ.get("PORT", 5000))
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")

    @staticmethod
    def validate():
        missing = [
            name
            for name in ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "JWT_SECRET"]
            if not os.environ.get(name)
        ]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Copy .env.example to .env and fill them in."
            )
