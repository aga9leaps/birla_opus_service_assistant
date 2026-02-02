"""
Birla Opus Chatbot - Database Connection
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool
from contextlib import contextmanager
import os

from config.settings import get_settings
from src.data.models import Base

settings = get_settings()


def get_database_url() -> str:
    """Get database URL from settings or environment."""
    return os.getenv("DATABASE_URL", settings.DATABASE_URL)


def create_db_engine():
    """Create database engine with appropriate settings for SQLite or PostgreSQL."""
    db_url = get_database_url()

    if db_url.startswith("sqlite"):
        # SQLite configuration - simpler pooling
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.DEBUG,
        )
    else:
        # PostgreSQL configuration - full pooling
        return create_engine(
            db_url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=settings.DEBUG,
        )


# Create engine
engine = create_db_engine()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session for FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def check_db_connection() -> bool:
    """Check if database connection is working."""
    try:
        with get_db_context() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False
