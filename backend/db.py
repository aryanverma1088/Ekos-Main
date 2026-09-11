import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///../data/processed/ekos.db")

# SQLite path in .env is relative to backend/, resolve it to an absolute path
# so scripts run from any working directory (e.g. scripts/) still hit the same file.
if DATABASE_URL.startswith("sqlite:///../"):
    rel = DATABASE_URL.replace("sqlite:///", "")
    abs_path = (BACKEND_DIR / rel).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{abs_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """Create all tables. Safe to call repeatedly (no-op if tables exist)."""
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()


if __name__ == "__main__":
    init_db()
    print(f"EKOS database initialized at: {DATABASE_URL}")
