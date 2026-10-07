import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "mysql+pymysql://{user}:{password}@{host}:{port}/{database}".format(
            user=os.environ.get("MYSQL_USER", "skillbridge"),
            password=os.environ.get("MYSQL_PASSWORD", "skillbridge"),
            host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
            port=os.environ.get("MYSQL_PORT", "3306"),
            database=os.environ.get("MYSQL_DATABASE", "skillbridge"),
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "development-only-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_MINUTES", "480")))
    CORS_ORIGINS = [origin.strip() for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")]
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    LEGACY_OTP_BASE_URL = os.environ.get("LEGACY_OTP_BASE_URL", "http://127.0.0.1:3000")
