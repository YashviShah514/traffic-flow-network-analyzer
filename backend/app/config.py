import os

from dotenv import load_dotenv

load_dotenv()


def database_url() -> str:
    """DATABASE_URL (PostgreSQL in production). Falls back to a local SQLite file for dev."""
    url = os.getenv("DATABASE_URL", "sqlite:///./traffic.db")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]
