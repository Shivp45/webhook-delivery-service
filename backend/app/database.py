"""
database.py
-----------
SQLAlchemy 2.0 engine, session factory, and Base class.
Both FastAPI and the Celery worker import from this module.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Read the DATABASE_URL from environment (set via Docker Compose or .env)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://webhook_user:webhook_pass@localhost:5432/webhook_db",
)

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session factory — each request or task gets its own session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """
    FastAPI dependency that yields a database session and
    ensures it is closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
