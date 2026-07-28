"""
Database engine and session setup.

Railway's Postgres addon injects a DATABASE_URL environment variable
automatically once you attach it to this service - nothing to configure
manually beyond attaching the addon in the Railway dashboard.

For local development without Postgres running, this falls back to a SQLite
file (backend/local_dev.db) so you can test signup/login without any extra
setup.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local_dev.db")

# Railway (and some other providers) hand out URLs starting with "postgres://",
# but SQLAlchemy 2.x requires the "postgresql://" scheme.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Creates all tables if they don't already exist. Called once at startup."""
    import models  # noqa: F401 - ensures models are registered on Base before create_all
    Base.metadata.create_all(bind=engine)
